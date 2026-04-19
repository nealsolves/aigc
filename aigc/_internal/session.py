"""
GovernanceSession and SessionPreCallResult — v0.9.0 workflow primitives.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from aigc._internal.errors import (
    InvocationValidationError,
    SessionStateError,
)
from aigc._internal.sinks import emit_to_sink

if TYPE_CHECKING:
    from aigc._internal.enforcement import AIGC

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifecycle constants
# ---------------------------------------------------------------------------

STATE_OPEN = "OPEN"
STATE_PAUSED = "PAUSED"
STATE_FAILED = "FAILED"
STATE_COMPLETED = "COMPLETED"
STATE_CANCELED = "CANCELED"
STATE_FINALIZED = "FINALIZED"

TERMINAL_STATES = {STATE_FAILED, STATE_COMPLETED, STATE_CANCELED}
PRE_TERMINAL_STATES = {STATE_OPEN, STATE_PAUSED}

# Maps session state → workflow artifact status
_ARTIFACT_STATUS_MAP = {
    STATE_COMPLETED: "COMPLETED",
    STATE_FAILED: "FAILED",
    STATE_CANCELED: "CANCELED",
    STATE_OPEN: "INCOMPLETE",
    STATE_PAUSED: "INCOMPLETE",
}

# Valid forward transitions: from_state → allowed to_states
_VALID_TRANSITIONS: dict[str, set[str]] = {
    STATE_OPEN: {STATE_PAUSED, STATE_FAILED, STATE_COMPLETED, STATE_CANCELED},
    STATE_PAUSED: {STATE_OPEN, STATE_FAILED, STATE_COMPLETED, STATE_CANCELED},
    STATE_FAILED: set(),
    STATE_COMPLETED: set(),
    STATE_CANCELED: set(),
    STATE_FINALIZED: set(),
}


# ---------------------------------------------------------------------------
# SessionPreCallResult — step ticket, no _inner
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SessionPreCallResult:
    """Single-use step token from GovernanceSession.enforce_step_pre_call().

    The inner PreCallResult is NOT stored here — it lives in
    GovernanceSession._pending_results.  Cannot be completed through the
    module-level enforce_post_call(); use GovernanceSession.enforce_step_post_call().
    """

    _IS_SESSION_TOKEN: ClassVar[bool] = True  # sentinel for enforce_post_call guards

    session_id: str
    step_id: str
    participant_id: str | None
    _token_id: str = field(repr=False)
    # Frozen bypass: _consumed starts False and is set to True exactly once by
    # the owning GovernanceSession via object.__setattr__. The frozen constraint
    # is intentional for all other fields; this field is lifecycle state, not
    # immutable data.
    _consumed: bool = field(default=False, init=False, repr=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _checksum(artifact: dict) -> str:
    """SHA-256 hex digest of canonical JSON."""
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _compute_policy_file(
    session_policy_file: str | None,
    step_policy_files: list[str | None],
) -> str | None:
    """Compute artifact policy_file per the finalization normalization rule.

    Priority order:
    0. No steps completed (empty list) → null
    1. Session-level override set → that value
    2. All steps used the same effective policy_file → that value
    3. Heterogeneous step policies → null
    """
    if not step_policy_files:
        # Rule 0: no completed steps
        return None
    if session_policy_file is not None:
        # Rule 1: session-level override always wins
        return session_policy_file
    unique = set(step_policy_files)
    if len(unique) == 1:
        # Rule 2: all steps used the same policy
        return next(iter(unique))
    # Rule 3: heterogeneous
    return None


# ---------------------------------------------------------------------------
# GovernanceSession
# ---------------------------------------------------------------------------

class GovernanceSession:
    """Context manager for governed multi-step workflow sessions.

    Obtained via ``AIGC.open_session()``. Manages the lifecycle::

        OPEN → PAUSED | FAILED | COMPLETED | CANCELED → FINALIZED

    ``__exit__`` never suppresses exceptions.  Clean exit from a pre-terminal
    state auto-finalizes to INCOMPLETE.  Exception exit records failure context,
    transitions to FAILED, emits a FAILED workflow artifact, and re-raises.
    """

    def __init__(
        self,
        aigc: "AIGC",
        session_id: str,
        policy_file: str | None,
        metadata: dict | None,
    ) -> None:
        self._aigc = aigc
        self._session_id = session_id
        self._policy_file = policy_file
        self._metadata = dict(metadata or {})

        self._state = STATE_OPEN
        self._started_at = int(time.time())
        self._finalized_at: int | None = None

        # token_id → {"inner": PreCallResult, "step_id": str,
        #              "participant_id": str | None,
        #              "effective_policy_file": str | None,
        #              "tool_calls_count": int}
        self._pending_results: dict[str, dict[str, Any]] = {}
        self._consumed_token_ids: set[str] = set()

        # Ordered step records for the workflow artifact
        self._steps: list[dict[str, Any]] = []
        # Effective policy_file per completed step (for normalization rule)
        self._step_policy_files: list[str | None] = []

        self._failure_summary: dict[str, Any] | None = None
        self._workflow_artifact: dict[str, Any] | None = None

        # Approval checkpoint records — populated by pause()/resume()
        self._approval_records: list[dict[str, Any]] = []

        # ValidatorHooks evaluated at each enforce_step_pre_call (internal-only
        # contract wired from the owning AIGC instance).
        self._validator_hooks: list[Any] = list(
            getattr(self._aigc, "_validator_hooks", ())
        )
        # Evidence records for the workflow artifact
        self._validator_hook_evidence: list[dict[str, Any]] = []

        # Workflow budget constraints and policy fields — loaded via AIGC's own cache+loader
        # (Fix 1: never call load_policy() directly here, which would bypass any custom loader)
        # Initialize defaults first (for when policy_file is None or load fails)
        self._max_steps: int | None = None
        self._max_total_tool_calls: int | None = None
        self._participants: list[dict] | None = None
        self._participants_by_id: dict[str, dict] = {}
        self._required_sequence: list[str] | None = None
        self._allowed_transitions: dict[str, list[str]] | None = None
        self._allowed_agent_roles: list[str] | None = None
        self._handoffs: list[dict] | None = None
        self._escalation: dict | None = None
        self._protocol_constraints: dict | None = None
        self._sequence_position: int = 0
        self._last_completed_step_id: str | None = None
        self._last_completed_participant_id: str | None = None

        if policy_file is not None:
            try:
                _policy = self._aigc._policy_cache.get_or_load(
                    policy_file,
                    loader=self._aigc._policy_loader,
                )
                _wf = _policy.get("workflow") or {}
                self._max_steps = _wf.get("max_steps")
                self._max_total_tool_calls = _wf.get("max_total_tool_calls")
                self._participants = _wf.get("participants")
                self._participants_by_id = {
                    p["id"]: p for p in (self._participants or [])
                }
                self._required_sequence = _wf.get("required_sequence")
                self._allowed_transitions = _wf.get("allowed_transitions")
                self._allowed_agent_roles = _wf.get("allowed_agent_roles")
                self._handoffs = _wf.get("handoffs")
                self._escalation = _wf.get("escalation")
                self._protocol_constraints = _wf.get("protocol_constraints")
            except Exception:  # noqa: BLE001
                pass  # Policy load failure surfaces at step enforcement time

        # Budget counters
        self._authorized_step_count: int = 0
        self._total_tool_calls_consumed: int = 0

        # Escalation re-fire guard: True while an escalation is pending approval
        # for the current step. Cleared in enforce_step_post_call on success.
        self._escalation_in_progress: bool = False

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def state(self) -> str:
        return self._state

    @property
    def workflow_artifact(self) -> dict[str, Any] | None:
        return self._workflow_artifact

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "GovernanceSession":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        if self._state == STATE_FINALIZED:
            return False  # already finalized

        if exc_type is not None:
            # Exception path: move to FAILED and record context
            if self._state not in TERMINAL_STATES:
                self._failure_summary = {
                    "exception_type": exc_type.__name__,
                    "message": str(exc_val),
                }
                self._state = STATE_FAILED
            # Suppress sink errors here — original exception must take precedence
            try:
                self._do_finalize()
            except Exception:  # noqa: BLE001
                logger.error(
                    "Workflow artifact sink emission failed during exception cleanup "
                    "for session %s (original exception takes precedence)",
                    self._session_id,
                )
        else:
            # Clean exit: respect failure_mode so on_sink_failure="raise" propagates
            self._do_finalize()

        return False  # never suppress exceptions

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def _assert_accepting_new_step(self) -> None:
        """Reject step authorization unless the session is OPEN (not PAUSED)."""
        if self._state != STATE_OPEN:
            raise SessionStateError(
                f"Session is not accepting new steps (state={self._state!r}); "
                f"call resume() first if the session is PAUSED",
                details={"session_id": self._session_id, "state": self._state},
            )

    def _assert_open(self) -> None:
        """Reject step completion unless the session is OPEN or PAUSED."""
        if self._state not in PRE_TERMINAL_STATES:
            raise SessionStateError(
                f"Session is not accepting steps (state={self._state!r})",
                details={"session_id": self._session_id, "state": self._state},
            )

    def _transition(self, to_state: str) -> None:
        allowed = _VALID_TRANSITIONS.get(self._state, set())
        if to_state not in allowed:
            raise SessionStateError(
                f"Invalid session transition: {self._state!r} → {to_state!r}",
                details={
                    "session_id": self._session_id,
                    "from_state": self._state,
                    "to_state": to_state,
                },
            )
        self._state = to_state

    def pause(
        self,
        *,
        approval_id: str | None = None,
        approver_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Pause the session (OPEN → PAUSED) and record an approval checkpoint."""
        self._transition(STATE_PAUSED)
        checkpoint: dict[str, Any] = {
            "checkpoint_id": approval_id or str(uuid.uuid4()),
            "paused_at": int(time.time()),
            "approver_id": approver_id,
            "reason": reason,
            "status": "pending",
            "resumed_at": None,
            "approval_note": None,
            "denial_reason": None,
        }
        self._approval_records.append(checkpoint)

    def resume(
        self,
        *,
        approval_id: str | None = None,
        approver_id: str | None = None,
        approval_note: str | None = None,
    ) -> None:
        """Resume a paused session (PAUSED → OPEN) and close the pending checkpoint.

        Fix 5: if approval_id is supplied it must match the pending checkpoint's
        checkpoint_id — mismatched IDs are rejected with SessionStateError.
        """
        if self._state != STATE_PAUSED:
            raise SessionStateError(
                f"resume() requires a PAUSED session (state={self._state!r})",
                details={
                    "session_id": self._session_id,
                    "current_state": self._state,
                },
            )

        pending = [
            rec for rec in reversed(self._approval_records) if rec["status"] == "pending"
        ]
        if not pending:
            raise SessionStateError(
                "resume() requires a pending approval checkpoint",
                details={
                    "session_id": self._session_id,
                    "current_state": self._state,
                    "pending_approval_ids": [],
                },
            )

        target = pending[0]
        if approval_id is not None:
            target = next(
                (rec for rec in pending if rec["checkpoint_id"] == approval_id),
                None,
            )
            if target is None:
                raise SessionStateError(
                    f"approval_id mismatch: expected {pending[0]['checkpoint_id']!r}, "
                    f"got {approval_id!r}",
                    details={
                        "session_id": self._session_id,
                        "expected_approval_id": pending[0]["checkpoint_id"],
                        "pending_approval_ids": [rec["checkpoint_id"] for rec in pending],
                        "provided_approval_id": approval_id,
                    },
                )

        self._transition(STATE_OPEN)
        target["status"] = "approved"
        target["resumed_at"] = int(time.time())
        if approver_id is not None:
            target["approver_id"] = approver_id
        target["approval_note"] = approval_note

    def deny_approval(
        self,
        *,
        approval_id: str | None = None,
        approver_id: str | None = None,
        denial_reason: str | None = None,
    ) -> None:
        """Deny a pending approval checkpoint. Session remains PAUSED."""
        # State guard: must be PAUSED with at least one pending checkpoint
        _pending = [r for r in self._approval_records if r["status"] == "pending"]
        if self._state != STATE_PAUSED or not _pending:
            raise SessionStateError(
                f"deny_approval() requires a PAUSED session with a pending checkpoint "
                f"(state={self._state!r})",
                details={
                    "session_id": self._session_id,
                    "current_state": self._state,
                },
            )
        # Find target checkpoint
        if approval_id is not None:
            target = next(
                (r for r in self._approval_records
                 if r["checkpoint_id"] == approval_id and r["status"] == "pending"),
                None,
            )
            if target is None:
                raise SessionStateError(
                    f"No pending checkpoint with approval_id={approval_id!r}",
                    details={
                        "session_id": self._session_id,
                        "approval_id": approval_id,
                    },
                )
        else:
            # Most recent pending
            target = _pending[-1]
        target["status"] = "denied"
        if approver_id is not None:
            target["approver_id"] = approver_id
        target["denial_reason"] = denial_reason
        target["resumed_at"] = None
        # Session stays PAUSED — do NOT transition

    def complete(self) -> None:
        """Mark the session as successfully completed (OPEN/PAUSED → COMPLETED)."""
        for rec in self._approval_records:
            if rec["status"] != "approved":
                raise SessionStateError(
                    f"Cannot complete session with unresolved approval checkpoint"
                    f" {rec['checkpoint_id']!r} (status={rec['status']!r})",
                    details={
                        "session_id": self._session_id,
                        "unresolved_checkpoint_id": rec["checkpoint_id"],
                        "checkpoint_status": rec["status"],
                    },
                )
        self._transition(STATE_COMPLETED)

    def cancel(self) -> None:
        """Cancel the session (OPEN/PAUSED → CANCELED)."""
        self._transition(STATE_CANCELED)

    def finalize(self) -> dict[str, Any]:
        """Explicitly finalize and emit the workflow artifact.

        May be called from any non-finalized state. OPEN or PAUSED emits
        ``INCOMPLETE``; terminal states emit their corresponding status.
        """
        if self._state == STATE_FINALIZED:
            raise SessionStateError(
                "Session is already finalized",
                details={"session_id": self._session_id},
            )
        return self._do_finalize()

    def _do_finalize(self) -> dict[str, Any]:
        """Internal finalization — emits artifact and transitions to FINALIZED."""
        self._finalized_at = int(time.time())

        artifact_status = _ARTIFACT_STATUS_MAP.get(self._state, "INCOMPLETE")
        policy_file = _compute_policy_file(
            self._policy_file,
            self._step_policy_files,
        )

        artifact: dict[str, Any] = {
            "workflow_schema_version": "0.9.0",
            "artifact_type": "workflow",
            "session_id": self._session_id,
            "policy_file": policy_file,
            "status": artifact_status,
            "started_at": self._started_at,
            "finalized_at": self._finalized_at,
            "steps": list(self._steps),
            "invocation_audit_checksums": [
                s["invocation_artifact_checksum"] for s in self._steps
            ],
            "failure_summary": self._failure_summary,
            "approval_checkpoints": list(self._approval_records),
            "validator_hook_evidence": list(self._validator_hook_evidence),
            "metadata": self._metadata,
        }

        self._workflow_artifact = artifact
        self._state = STATE_FINALIZED

        emit_to_sink(
            artifact,
            sink=self._aigc._sink,
            failure_mode=self._aigc._on_sink_failure,
        )

        return artifact

    # ------------------------------------------------------------------
    # Step enforcement
    # ------------------------------------------------------------------

    def _assert_owns(self, session_result: SessionPreCallResult) -> None:
        if session_result.session_id != self._session_id:
            raise InvocationValidationError(
                "Token belongs to a different session",
                details={
                    "token_session_id": session_result.session_id,
                    "this_session_id": self._session_id,
                },
            )

    def enforce_step_pre_call(
        self,
        invocation: dict[str, Any],
        *,
        step_id: str | None = None,
        participant_id: str | None = None,
    ) -> SessionPreCallResult:
        """Enforce Phase A governance for one workflow step.

        :param invocation: Invocation dict (same fields as enforce_pre_call)
        :param step_id: Caller-supplied step identifier; UUID4 generated if omitted
        :param participant_id: Optional participant identifier
        :return: SessionPreCallResult token (pass to enforce_step_post_call)
        """
        self._assert_accepting_new_step()

        # Budget check: max_steps (Fix 4: raise WorkflowStepBudgetExceededError,
        # not WorkflowToolBudgetExceededError, so doctor gives the right remediation)
        if (
            self._max_steps is not None
            and self._authorized_step_count >= self._max_steps
        ):
            from aigc._internal.errors import WorkflowStepBudgetExceededError
            raise WorkflowStepBudgetExceededError(
                f"Session step budget exceeded: max_steps={self._max_steps}, "
                f"authorized={self._authorized_step_count}",
                details={
                    "session_id": self._session_id,
                    "max_steps": self._max_steps,
                    "authorized_step_count": self._authorized_step_count,
                },
            )

        resolved_step_id = step_id or str(uuid.uuid4())

        # 5A1: Participant enforcement
        if self._participants_by_id:
            from aigc._internal.errors import WorkflowParticipantMismatchError
            if participant_id is None:
                raise WorkflowParticipantMismatchError(
                    "participants declared in policy but no participant_id supplied for this step",
                    details={
                        "session_id": self._session_id,
                        "step_id": resolved_step_id,
                        "reason_code": "WORKFLOW_PARTICIPANT_ID_REQUIRED",
                    },
                )
            if participant_id not in self._participants_by_id:
                raise WorkflowParticipantMismatchError(
                    f"participant_id={participant_id!r} not in declared participants",
                    details={
                        "session_id": self._session_id,
                        "step_id": resolved_step_id,
                        "participant_id": participant_id,
                        "declared_participant_ids": list(self._participants_by_id),
                    },
                )
            _part = self._participants_by_id[participant_id]
            _part_roles = _part.get("roles")
            _invoc_role = invocation.get("role")
            if _part_roles and _invoc_role not in _part_roles:
                raise WorkflowParticipantMismatchError(
                    f"invocation role={_invoc_role!r} not in participant "
                    f"{participant_id!r} allowed roles: {_part_roles}",
                    details={
                        "session_id": self._session_id,
                        "participant_id": participant_id,
                        "invocation_role": _invoc_role,
                        "allowed_roles": _part_roles,
                        "reason_code": "WORKFLOW_PARTICIPANT_ROLE_MISMATCH",
                    },
                )

        # 5B: Required sequence enforcement
        if (
            self._required_sequence is not None
            and self._sequence_position < len(self._required_sequence)
        ):
            from aigc._internal.errors import WorkflowSequenceViolationError
            expected_step_id = self._required_sequence[self._sequence_position]
            if step_id is None:
                raise WorkflowSequenceViolationError(
                    f"required_sequence declared: step_id is required at position "
                    f"{self._sequence_position} (expected {expected_step_id!r})",
                    details={
                        "session_id": self._session_id,
                        "sequence_position": self._sequence_position,
                        "expected_step_id": expected_step_id,
                        "reason_code": "WORKFLOW_SEQUENCE_STEP_ID_REQUIRED",
                    },
                )
            if resolved_step_id != expected_step_id:
                raise WorkflowSequenceViolationError(
                    f"required_sequence violation: expected "
                    f"step_id={expected_step_id!r} at position "
                    f"{self._sequence_position}, got {resolved_step_id!r}",
                    details={
                        "session_id": self._session_id,
                        "sequence_position": self._sequence_position,
                        "expected_step_id": expected_step_id,
                        "actual_step_id": resolved_step_id,
                    },
                )
            # Do NOT advance _sequence_position here — advance in post_call on success

        # 5C: Allowed transitions enforcement
        if self._allowed_transitions is not None and self._last_completed_step_id is not None:
            from aigc._internal.errors import WorkflowTransitionDeniedError
            if step_id is None:
                raise WorkflowTransitionDeniedError(
                    "allowed_transitions declared: step_id is required to verify transition",
                    details={
                        "session_id": self._session_id,
                        "last_completed_step_id": self._last_completed_step_id,
                        "reason_code": "WORKFLOW_TRANSITION_STEP_ID_REQUIRED",
                    },
                )
            _allowed_to = self._allowed_transitions.get(self._last_completed_step_id, [])
            if resolved_step_id not in _allowed_to:
                raise WorkflowTransitionDeniedError(
                    f"Transition from {self._last_completed_step_id!r} to {resolved_step_id!r} "
                    f"is not in allowed_transitions",
                    details={
                        "session_id": self._session_id,
                        "from_step_id": self._last_completed_step_id,
                        "to_step_id": resolved_step_id,
                        "allowed_transitions": _allowed_to,
                    },
                )
        # Note: first step (_last_completed_step_id is None) has no transition check

        # 5D: Allowed agent roles enforcement
        if self._allowed_agent_roles is not None:
            from aigc._internal.errors import WorkflowRoleViolationError
            _invoc_role = invocation.get("role")
            if _invoc_role not in self._allowed_agent_roles:
                raise WorkflowRoleViolationError(
                    f"invocation role={_invoc_role!r} not in "
                    f"allowed_agent_roles: {self._allowed_agent_roles}",
                    details={
                        "session_id": self._session_id,
                        "step_id": resolved_step_id,
                        "invocation_role": _invoc_role,
                        "allowed_agent_roles": self._allowed_agent_roles,
                    },
                )

        # 5E: Protocol constraints enforcement
        if self._protocol_constraints is not None:
            from aigc._internal.errors import WorkflowProtocolViolationError
            _protocol = invocation.get("protocol") or (
                invocation.get("context") or {}
            ).get("protocol")
            if _protocol is None:
                raise WorkflowProtocolViolationError(
                    "protocol_constraints declared but no protocol specified in invocation "
                    "(set invocation['protocol'] or invocation['context']['protocol'])",
                    details={
                        "session_id": self._session_id,
                        "step_id": resolved_step_id,
                        "reason_code": "WORKFLOW_PROTOCOL_REQUIRED",
                    },
                )
            if _protocol not in self._protocol_constraints:
                raise WorkflowProtocolViolationError(
                    f"Protocol {_protocol!r} not in declared protocol_constraints sections: "
                    f"{list(self._protocol_constraints)}",
                    details={
                        "session_id": self._session_id,
                        "step_id": resolved_step_id,
                        "protocol": _protocol,
                        "declared_protocols": list(self._protocol_constraints),
                    },
                )
            _ctx = invocation.get("context") or {}
            _proto_evidence = _ctx.get("protocol_evidence")
            if not isinstance(_proto_evidence, dict) or _protocol not in _proto_evidence:
                raise WorkflowProtocolViolationError(
                    f"No evidence for protocol {_protocol!r} in context['protocol_evidence']",
                    details={
                        "session_id": self._session_id,
                        "step_id": resolved_step_id,
                        "protocol": _protocol,
                    },
                )
            # Participant protocol check
            if participant_id and self._participants_by_id:
                _part = self._participants_by_id.get(participant_id)
                if _part:
                    _part_protos = _part.get("protocols")
                    if _part_protos and _protocol not in _part_protos:
                        raise WorkflowProtocolViolationError(
                            f"Protocol {_protocol!r} not in participant "
                            f"{participant_id!r} allowed protocols",
                            details={
                                "session_id": self._session_id,
                                "participant_id": participant_id,
                                "protocol": _protocol,
                                "allowed_protocols": _part_protos,
                            },
                        )
            # Protocol-family-specific runtime checks
            _evidence_for_protocol = _proto_evidence.get(_protocol, {})
            if _protocol == "bedrock":
                # Alias-backed identity required when participant declares bedrock protocol
                if participant_id and self._participants_by_id:
                    _part = self._participants_by_id.get(participant_id)
                    if _part and "bedrock" in (_part.get("protocols") or []):
                        if not _evidence_for_protocol.get("alias_backed"):
                            raise WorkflowProtocolViolationError(
                                "Bedrock governed binding requires alias-backed identity; "
                                "set context['protocol_evidence']"
                                "['bedrock']['alias_backed'] = True",
                                details={
                                    "session_id": self._session_id,
                                    "participant_id": participant_id,
                                    "protocol": "bedrock",
                                },
                            )
            elif _protocol == "a2a":
                # gRPC transport is out of scope for v0.9.0
                if _evidence_for_protocol.get("transport") == "grpc":
                    raise WorkflowProtocolViolationError(
                        "gRPC transport is not supported for a2a in v0.9.0",
                        details={
                            "session_id": self._session_id,
                            "protocol": "a2a",
                            "transport": "grpc",
                        },
                    )
                # Require supportedInterfaces with protocolVersion "1.0"
                _interfaces = _evidence_for_protocol.get("supportedInterfaces") or []
                if not any(
                    isinstance(i, dict) and i.get("protocolVersion") == "1.0"
                    for i in _interfaces
                ):
                    raise WorkflowProtocolViolationError(
                        "A2A evidence must include supportedInterfaces[] entry with "
                        "protocolVersion == '1.0'",
                        details={
                            "session_id": self._session_id,
                            "protocol": "a2a",
                        },
                    )

        # 5F: Handoffs enforcement
        if (
            self._handoffs is not None
            and self._last_completed_participant_id is not None
            and participant_id is not None
            and self._last_completed_participant_id != participant_id
        ):
            from aigc._internal.errors import WorkflowHandoffDeniedError
            _allowed_handoffs = {(h["from"], h["to"]) for h in self._handoffs}
            if (self._last_completed_participant_id, participant_id) not in _allowed_handoffs:
                raise WorkflowHandoffDeniedError(
                    f"Handoff from participant {self._last_completed_participant_id!r} to "
                    f"{participant_id!r} is not in allowed handoffs",
                    details={
                        "session_id": self._session_id,
                        "from_participant_id": self._last_completed_participant_id,
                        "to_participant_id": participant_id,
                    },
                )

        # 5G: Escalation enforcement
        if self._escalation is not None and self._state == STATE_OPEN:
            from aigc._internal.errors import WorkflowApprovalRequiredError
            _esc_n = self._escalation.get("require_approval_after_steps")
            _esc_roles = self._escalation.get("require_approval_for_roles") or []
            _invoc_role_esc = invocation.get("role")
            _need_approval = False
            _esc_reason = None
            _esc_rule = None
            # Skip re-firing escalation if already in progress for this step
            # (post-resume retry). Once the step succeeds in enforce_step_post_call,
            # _escalation_in_progress is cleared so the next trigger fires normally.
            if self._escalation_in_progress:
                _need_approval = False
            else:
                if (
                    _esc_n is not None
                    and self._authorized_step_count > 0
                    and self._authorized_step_count % _esc_n == 0
                ):
                    _need_approval = True
                    _esc_reason = f"Escalation: approval required after every {_esc_n} steps"
                    _esc_rule = f"require_approval_after_steps={_esc_n}"
                if _esc_roles and _invoc_role_esc in _esc_roles:
                    _need_approval = True
                    _esc_reason = f"Escalation: approval required for role {_invoc_role_esc!r}"
                    _esc_rule = f"require_approval_for_roles includes {_invoc_role_esc!r}"
            if _need_approval:
                _esc_checkpoint_id = str(uuid.uuid4())
                self._escalation_in_progress = True
                self.pause(
                    approval_id=_esc_checkpoint_id,
                    reason=_esc_reason,
                )
                raise WorkflowApprovalRequiredError(
                    _esc_reason or "Escalation: approval required",
                    details={
                        "session_id": self._session_id,
                        "checkpoint_id": _esc_checkpoint_id,
                        "escalation_rule": _esc_rule,
                    },
                )

        token_id = str(uuid.uuid4())

        # Build enriched invocation: apply session-level policy override, then
        # inject workflow correlation fields into context
        enriched = dict(invocation)
        if self._policy_file is not None:
            enriched["policy_file"] = self._policy_file
        effective_policy_file: str | None = enriched.get("policy_file")

        ctx: dict[str, Any] = dict(enriched.get("context") or {})
        ctx["session_id"] = self._session_id
        ctx["step_id"] = resolved_step_id
        if participant_id is not None:
            ctx["participant_id"] = participant_id
        enriched["context"] = ctx

        # Budget check: max_total_tool_calls counted from invocation at pre_call time
        # (Fix 2: invocation-time count matches existing tools.py contract and audit
        # evidence — never count from output)
        _tool_calls_this_step = len(enriched.get("tool_calls") or [])
        _projected_total = self._total_tool_calls_consumed + _tool_calls_this_step
        if (
            self._max_total_tool_calls is not None
            and _projected_total > self._max_total_tool_calls
        ):
            from aigc._internal.errors import WorkflowToolBudgetExceededError
            raise WorkflowToolBudgetExceededError(
                f"Session tool-call budget exceeded: "
                f"max_total_tool_calls={self._max_total_tool_calls}, "
                f"projected={_projected_total}",
                details={
                    "session_id": self._session_id,
                    "max_total_tool_calls": self._max_total_tool_calls,
                    "total_tool_calls_consumed": self._total_tool_calls_consumed,
                    "tool_calls_this_step": _tool_calls_this_step,
                },
            )

        inner_result = self._aigc.enforce_pre_call(enriched)

        # Run validator hooks after invocation-level governance passes
        # (Fix 3: hooks are wired internally — validator_hooks is NOT a parameter of
        # the public AIGC.open_session(); Fix 4: raise WorkflowHookDeniedError, not
        # WorkflowApprovalRequiredError, so doctor gives the right remediation)
        if self._validator_hooks:
            from aigc._internal.validator_hook import (
                ValidatorHookEnvelope,
                _invoke_hook,
                VALIDATOR_DENY,
                VALIDATOR_TIMEOUT,
                VALIDATOR_REVIEW_REQUIRED,
            )
            from aigc._internal.errors import WorkflowHookDeniedError
            for _hook in self._validator_hooks:
                _obs_at = int(time.time() * 1000)
                _envelope = ValidatorHookEnvelope(
                    hook_schema_version="1.0",
                    session_id=self._session_id,
                    step_id=resolved_step_id,
                    participant_id=participant_id,
                    invocation=enriched,
                    deadline_ms=_hook.timeout_ms,
                    observed_at=_obs_at,
                    policy_file=effective_policy_file,
                    invocation_checksum=_checksum(enriched),
                )
                _result = _invoke_hook(_hook, _envelope)
                self._validator_hook_evidence.append({
                    "hook_id": _result.hook_id,
                    "hook_version": _result.hook_version,
                    "step_id": resolved_step_id,
                    "decision": _result.decision,
                    "reason_code": _result.reason_code,
                    "explanation": _result.explanation,
                    "attempt": _result.attempt,
                    "latency_ms": _result.latency_ms,
                    "observed_at": _result.observed_at,
                    "stale_result": _result.stale_result,
                    "provenance": _result.provenance,
                })
                if _result.decision in {
                    VALIDATOR_DENY, VALIDATOR_TIMEOUT, VALIDATOR_REVIEW_REQUIRED
                }:
                    raise WorkflowHookDeniedError(
                        f"Validator hook {_result.hook_id!r} blocked step "
                        f"{resolved_step_id!r}: decision={_result.decision!r}, "
                        f"reason_code={_result.reason_code!r}",
                        details={
                            "session_id": self._session_id,
                            "step_id": resolved_step_id,
                            "hook_id": _result.hook_id,
                            "decision": _result.decision,
                            "reason_code": _result.reason_code,
                        },
                    )
                # After fail-closed raise above, only ALLOW/WARN/EXECUTION_FAILURE
                # remain — all are safe to continue.

        self._pending_results[token_id] = {
            "inner": inner_result,
            "step_id": resolved_step_id,
            "participant_id": participant_id,
            "effective_policy_file": effective_policy_file,
            "tool_calls_count": _tool_calls_this_step,
        }

        # Increment only after all checks pass — pre-call rejection must not
        # corrupt the authorized step counter
        self._authorized_step_count += 1

        return SessionPreCallResult(
            session_id=self._session_id,
            step_id=resolved_step_id,
            participant_id=participant_id,
            _token_id=token_id,
        )

    def enforce_step_post_call(
        self,
        session_result: SessionPreCallResult,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        """Enforce Phase B governance for one workflow step.

        :param session_result: Token from enforce_step_pre_call
        :param output: Model output dict
        :return: Invocation PASS audit artifact
        """
        self._assert_open()
        self._assert_owns(session_result)

        if session_result._token_id in self._consumed_token_ids:
            raise InvocationValidationError(
                "Token already consumed",
                details={"token_id": session_result._token_id},
            )

        entry = self._pending_results.get(session_result._token_id)
        if entry is None:
            raise InvocationValidationError(
                "Token not registered in this session",
                details={"token_id": session_result._token_id},
            )

        # Verify token fields match minted values — rejects forged wrappers
        if (
            session_result.step_id != entry["step_id"]
            or session_result.participant_id != entry["participant_id"]
        ):
            raise InvocationValidationError(
                "Token fields do not match minted values — possible forged wrapper",
                details={
                    "token_step_id": session_result.step_id,
                    "registered_step_id": entry["step_id"],
                },
            )

        try:
            # Phase B FIRST — output validation
            inv_artifact = self._aigc.enforce_post_call(entry["inner"], output)
        except Exception:
            # A session token is single-use once Phase B has been attempted,
            # even if the inner invocation token failed before artifact emission.
            object.__setattr__(session_result, "_consumed", True)
            self._consumed_token_ids.add(session_result._token_id)
            self._pending_results.pop(session_result._token_id, None)
            raise

        # Validation succeeded — NOW mark consumed
        object.__setattr__(session_result, "_consumed", True)
        self._consumed_token_ids.add(session_result._token_id)
        del self._pending_results[session_result._token_id]

        # Increment tool-call counter from the invocation dict (consistent with
        # pre_call budget check — both use invocation-time count). Budget is
        # enforced entirely at pre-call; this increment can never exceed the limit.
        self._total_tool_calls_consumed += entry["tool_calls_count"]

        # Step record uses REGISTRY values — never trusts token fields after verification
        inv_checksum = _checksum(inv_artifact)
        self._steps.append({
            "step_id": entry["step_id"],
            "participant_id": entry["participant_id"],
            "invocation_artifact_checksum": inv_checksum,
        })
        self._step_policy_files.append(entry["effective_policy_file"])

        # Advance tracking state for sequence, transitions, and handoffs
        self._sequence_position += 1
        self._last_completed_step_id = entry["step_id"]
        self._last_completed_participant_id = entry["participant_id"]
        self._escalation_in_progress = False  # Step completed — clear escalation gate

        return inv_artifact
