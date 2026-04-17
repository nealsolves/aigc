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

from aigc._internal.errors import InvocationValidationError, SessionStateError
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
        #              "effective_policy_file": str | None}
        self._pending_results: dict[str, dict[str, Any]] = {}
        self._consumed_token_ids: set[str] = set()

        # Ordered step records for the workflow artifact
        self._steps: list[dict[str, Any]] = []
        # Effective policy_file per completed step (for normalization rule)
        self._step_policy_files: list[str | None] = []

        self._failure_summary: dict[str, Any] | None = None
        self._workflow_artifact: dict[str, Any] | None = None

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

    def pause(self) -> None:
        """Pause the session (OPEN → PAUSED)."""
        self._transition(STATE_PAUSED)

    def resume(self) -> None:
        """Resume a paused session (PAUSED → OPEN)."""
        self._transition(STATE_OPEN)

    def complete(self) -> None:
        """Mark the session as successfully completed (OPEN/PAUSED → COMPLETED)."""
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

        resolved_step_id = step_id or str(uuid.uuid4())
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

        inner_result = self._aigc.enforce_pre_call(enriched)

        self._pending_results[token_id] = {
            "inner": inner_result,
            "step_id": resolved_step_id,
            "participant_id": participant_id,
            "effective_policy_file": effective_policy_file,
        }

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

        # Phase B FIRST — output validation
        inv_artifact = self._aigc.enforce_post_call(entry["inner"], output)

        # Validation succeeded — NOW mark consumed
        object.__setattr__(session_result, "_consumed", True)
        self._consumed_token_ids.add(session_result._token_id)
        del self._pending_results[session_result._token_id]

        # Step record uses REGISTRY values — never trusts token fields after verification
        inv_checksum = _checksum(inv_artifact)
        self._steps.append({
            "step_id": entry["step_id"],
            "participant_id": entry["participant_id"],
            "invocation_artifact_checksum": inv_checksum,
        })
        self._step_policy_files.append(entry["effective_policy_file"])

        return inv_artifact
