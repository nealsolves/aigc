"""
Core enforcement logic.

Combines:
- policy loading
- validation
- error handling
- audit logging triggers
- audit sink emission
- risk scoring
- custom enforcement gates
- OpenTelemetry instrumentation
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac as _hmac_mod
import json
import logging
import os
import re
import time as _time
import types
from dataclasses import dataclass, field
from typing import Any, Mapping

import warnings

from aigc._internal.audit import DEFAULT_REDACTION_PATTERNS

from aigc._internal.policy_loader import (
    load_policy,
    PolicyCache,
    PolicyLoaderBase,
)
from aigc._internal.validator import (
    validate_postconditions,
    validate_preconditions,
    validate_role,
    validate_schema,
)
from aigc._internal.audit import generate_audit_artifact, sanitize_failure_message
from aigc._internal.guards import evaluate_guards
from aigc._internal.tools import validate_tool_constraints
from aigc._internal.sinks import emit_to_sink
from aigc._internal.risk_scoring import (
    compute_risk_score,
    RISK_MODE_STRICT,
    RISK_MODE_WARN_ONLY,
    RiskScore,
)
from aigc._internal.signing import ArtifactSigner, sign_artifact
from aigc._internal.gates import (
    EnforcementGate,
    run_gates,
    sort_gates,
    validate_gate,
    INSERTION_PRE_AUTHORIZATION,
    INSERTION_POST_AUTHORIZATION,
    INSERTION_PRE_OUTPUT,
    INSERTION_POST_OUTPUT,
)
from aigc._internal.telemetry import (
    enforcement_span,
    record_gate_event,
    record_enforcement_result,
)
from aigc._internal.errors import (
    AIGCError,
    AuditSinkError,
    ConditionResolutionError,
    CustomGateViolationError,
    FeatureNotImplementedError,
    GovernanceViolationError,
    GuardEvaluationError,
    InvocationValidationError,
    PolicyLoadError,
    PolicyValidationError,
    PreconditionError,
    RiskThresholdError,
    SchemaValidationError,
    ToolConstraintViolationError,
)

logger = logging.getLogger("aigc.enforcement")

# ── Canonical gate IDs (append-only; order matters) ──────────────
GATE_GUARDS = "guard_evaluation"
GATE_ROLE = "role_validation"
GATE_PRECONDS = "precondition_validation"
GATE_TOOLS = "tool_constraint_validation"
GATE_SCHEMA = "schema_validation"
GATE_POSTCONDS = "postcondition_validation"
GATE_RISK = "risk_scoring"

AUTHORIZATION_GATES = (GATE_GUARDS, GATE_ROLE, GATE_PRECONDS, GATE_TOOLS)
OUTPUT_GATES = (GATE_SCHEMA, GATE_POSTCONDS)


def _record_gate(gates: list[str], gate_id: str) -> None:
    """Append gate_id to the running gates_evaluated list (append-only)."""
    gates.append(gate_id)


# ── PreCallResult handoff token ──────────────────────────────────


class _EnforcementToken:
    """Singleton sentinel used as the provenance marker on PreCallResult.

    Provenance check threat model: misuse-detection only.
    This sentinel prevents accidental construction of PreCallResult outside
    enforce_pre_call() (e.g. typos, copy-paste errors). It does NOT prevent
    hostile in-process code that imports module internals — Python offers no
    language-level mechanism for that. Cross-process or multi-tenant isolation
    is the host's responsibility (spec Section 10.6).

    Pickle and deepcopy survival: __reduce__ and __deepcopy__ return the
    module-level singleton so identity-based checks remain valid after
    pickle round-trips and deepcopy operations (spec Section 10.5).
    """

    __slots__ = ()

    def __copy__(self) -> "_EnforcementToken":
        return self

    def __deepcopy__(self, _memo: dict) -> "_EnforcementToken":
        return self

    def __reduce__(self) -> tuple:
        # Unpickling calls _get_enforcement_token() which returns the
        # module-level singleton, preserving object identity.
        return (_get_enforcement_token, ())


def _get_enforcement_token() -> "_EnforcementToken":
    """Return the module-level _ENFORCEMENT_TOKEN singleton (pickle helper)."""
    return _ENFORCEMENT_TOKEN


# Module-private sentinel. Only code inside this module sets _origin to this
# value via object.__setattr__. A directly-constructed PreCallResult gets
# _origin=None (the field default) and is rejected by post-call.
_ENFORCEMENT_TOKEN: _EnforcementToken = _EnforcementToken()


def _make_token_signer() -> tuple:
    """Return (sign_fn, verify_fn) with the HMAC session key in a closure.

    The key is not exposed as a module-level attribute; extracting it requires
    explicit closure introspection rather than a straightforward import.
    Combined with the _origin sentinel check, this provides defense-in-depth
    against trivial in-process token forgery (audit Finding #1, 2026-04-05).

    Note: Python in-process security is inherently limited — a determined
    hostile caller with full module-import access can still bypass these
    checks via gc introspection.  The intended threat model is misuse
    detection (accidental direct construction, copy-paste errors), not
    adversarial in-process attackers.
    """
    _key = os.urandom(32)

    def _sign(payload: bytes) -> bytes:
        return _hmac_mod.digest(_key, payload, hashlib.sha256)

    def _verify(payload: bytes, digest: bytes) -> bool:
        if not isinstance(payload, bytes) or not isinstance(digest, bytes):
            return False
        try:
            expected = _hmac_mod.digest(_key, payload, hashlib.sha256)
            return _hmac_mod.compare_digest(expected, digest)
        except Exception:
            return False

    return _sign, _verify


_token_sign, _token_verify = _make_token_signer()

# Process-local registry of consumed token HMACs (Finding 3, 2026-04-05).
# Prevents replay via deepcopy/pickle clone of an unconsumed token.
# Keyed by _token_hmac bytes (unique per session key + evidence content).
# Thread safety: individual set.add/in operations are GIL-protected, but the
# check-then-add sequence (step 1f → step 5) is NOT atomic across threads.
# Concurrent calls with the same-token clone may both pass the check before
# either registers. Use external locking if calling from multiple threads.
# Threat model: process-local misuse detection (spec Section 10.6).
_consumed_token_registry: set[bytes] = set()


def _gate_fingerprint(grouped_gates: Any) -> dict[str, list[dict[str, str]]]:
    """Compute a JSON-serializable fingerprint of the gate manifest.

    Used to authenticate _phase_b_grouped_gates against signed evidence.
    Maps insertion point -> list of {name, insertion_point} dicts.
    """
    if grouped_gates is None:
        return {}
    result: dict[str, list[dict[str, str]]] = {}
    for pt, gates in grouped_gates.items():
        result[pt] = [
            {"name": g.name, "insertion_point": g.insertion_point}
            for g in gates
        ]
    return result


@dataclass(frozen=True, slots=True)
class PreCallResult:
    """Opaque handoff token from enforce_pre_call() to enforce_post_call().

    Logically immutable. One-time use only.
    Not public API directly -- exported via aigc.enforcement and aigc.__init__.
    """

    effective_policy: Mapping[str, Any]
    resolved_guards: tuple[dict[str, Any], ...]
    resolved_conditions: Mapping[str, Any]
    phase_a_metadata: Mapping[str, Any]
    invocation_snapshot: Mapping[str, Any]
    policy_file: str
    model_provider: str
    model_identifier: str
    role: str
    _consumed: bool = field(
        init=False, default=False, repr=False, compare=False,
    )
    # Sorted Phase B gates — set by enforce_pre_call, consumed by
    # enforce_post_call.  Stored here so the module-level split API
    # can carry custom gates across the pre/post boundary without
    # requiring callers to pass them again at post-call time.
    _phase_b_grouped_gates: Any = field(
        init=False, default=None, repr=False, compare=False,
    )
    # Provenance marker — set to _ENFORCEMENT_TOKEN only by this
    # module via object.__setattr__.  A directly-constructed PreCallResult
    # gets None here and is rejected by enforce_post_call.
    _origin: "_EnforcementToken | None" = field(
        init=False, default=None, repr=False, compare=False,
    )
    # Private deep-frozen copies taken at Phase A completion time.
    # Phase B reads exclusively from these, so caller mutations to
    # the public effective_policy / invocation_snapshot fields after
    # Phase A have no effect on Phase B enforcement.
    _frozen_effective_policy: Any = field(
        init=False, default=None, repr=False, compare=False,
    )
    _frozen_invocation_snapshot: Any = field(
        init=False, default=None, repr=False, compare=False,
    )
    # Canonical JSON serializations of Phase A state.  A bytes object
    # cannot have its contents mutated, so Phase B deserialization is
    # immune to any post-Phase-A mutations of _frozen_effective_policy
    # or phase_a_metadata (Findings 1 & 2, Round 2 audit).
    _frozen_policy_bytes: Any = field(
        init=False, default=None, repr=False, compare=False,
    )
    _frozen_phase_a_metadata: Any = field(
        init=False, default=None, repr=False, compare=False,
    )
    # Canonical JSON serialization of invocation_snapshot, phase_a_metadata,
    # guards_evaluated_engine, and conditions_resolved.  A bytes object cannot
    # be mutated, so Phase B deserialization is immune to any post-Phase-A
    # mutations of _frozen_invocation_snapshot, _frozen_phase_a_metadata,
    # resolved_guards, or resolved_conditions (Round 3 audit Finding 2).
    _frozen_evidence_bytes: Any = field(
        init=False, default=None, repr=False, compare=False,
    )
    # HMAC-SHA256 of _frozen_evidence_bytes, keyed by a session secret held
    # in the _make_token_signer() closure.  Phase B rejects tokens whose HMAC
    # does not verify, providing forgery resistance beyond the _origin sentinel
    # (audit Finding #1, 2026-04-05).  Default b"" is never a valid 32-byte
    # digest, so an un-signed token is rejected automatically.
    _token_hmac: bytes = field(
        init=False, default=b"", repr=False, compare=False,
    )

    def __getstate__(self) -> dict:
        """Pickle support: serialize all slots, converting MappingProxyType to dict."""
        state = {
            slot: getattr(self, slot)
            for slot in self.__slots__
            if hasattr(self, slot)
        }
        # MappingProxyType is not picklable; convert to plain dict with
        # list values so __setstate__ can rebuild the immutable proxy.
        gates = state.get("_phase_b_grouped_gates")
        if isinstance(gates, types.MappingProxyType):
            state["_phase_b_grouped_gates"] = {
                pt: list(gl) for pt, gl in gates.items()
            }
        return state

    def __setstate__(self, state: dict) -> None:
        """Pickle support: restore all slots, re-wrapping gates as MappingProxyType."""
        for key, value in state.items():
            object.__setattr__(self, key, value)
        # Re-wrap gates in the immutable proxy that __getstate__ flattened.
        gates = state.get("_phase_b_grouped_gates")
        if isinstance(gates, dict):
            object.__setattr__(
                self,
                "_phase_b_grouped_gates",
                types.MappingProxyType(
                    {pt: tuple(gl) for pt, gl in gates.items()}
                ),
            )


# ── Invocation validation (three layers) ─────────────────────────

REQUIRED_CORE_KEYS = (
    "policy_file",
    "model_provider",
    "model_identifier",
    "role",
    "input",
    "context",
)

REQUIRED_INVOCATION_KEYS = REQUIRED_CORE_KEYS + ("output",)


def _validate_invocation_core(invocation: Mapping[str, Any]) -> None:
    """Validate fields common to both unified and pre-call invocations."""
    if not isinstance(invocation, Mapping):
        raise InvocationValidationError(
            "Invocation must be a mapping object",
            details={"received_type": type(invocation).__name__},
        )
    missing = [key for key in REQUIRED_CORE_KEYS if key not in invocation]
    if missing:
        raise InvocationValidationError(
            "Invocation is missing required fields",
            details={"missing_fields": missing},
        )

    string_keys = ("policy_file", "model_provider", "model_identifier", "role")
    for key in string_keys:
        if not isinstance(invocation[key], str) or not invocation[key]:
            raise InvocationValidationError(
                f"Invocation field '{key}' must be a non-empty string",
                details={"field": key},
            )

    for key in ("input", "context"):
        if not isinstance(invocation[key], dict):
            raise InvocationValidationError(
                f"Invocation field '{key}' must be an object",
                details={"field": key},
            )

    for key in ("input", "context"):
        try:
            json.dumps(invocation[key], allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as e:
            raise InvocationValidationError(
                f"Invocation field '{key}' is not JSON-serializable: {e}",
                details={"field": key},
            ) from e


def _validate_invocation(invocation: Mapping[str, Any]) -> None:
    """Validate a complete unified invocation (requires output)."""
    _validate_invocation_core(invocation)
    if "output" not in invocation:
        raise InvocationValidationError(
            "Invocation is missing required fields",
            details={"missing_fields": ["output"]},
        )
    if not isinstance(invocation["output"], dict):
        raise InvocationValidationError(
            "Invocation field 'output' must be an object",
            details={"field": "output"},
        )
    try:
        json.dumps(invocation["output"], allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as e:
        raise InvocationValidationError(
            f"Invocation field 'output' is not JSON-serializable: {e}",
            details={"field": "output"},
        ) from e


def _validate_pre_call_invocation(invocation: Mapping[str, Any]) -> None:
    """Validate a pre-call invocation (output not required or used)."""
    _validate_invocation_core(invocation)


def _map_exception_to_failure_gate(exc: Exception) -> str:
    """Map exception type to failure gate identifier.

    Check subclasses before parent classes to ensure correct mapping.
    All returned values must be members of the failure_gate enum in
    schemas/audit_artifact.schema.json.
    """
    # Check subclasses before parent classes to ensure correct mapping.
    if isinstance(exc, FeatureNotImplementedError):
        return "feature_not_implemented"
    if isinstance(exc, InvocationValidationError):
        return "invocation_validation"
    if isinstance(exc, PolicyValidationError):
        # Risk-config validation errors carry "invalid_mode" in details;
        # route them to the risk_scoring gate for triage fidelity.
        if (
            isinstance(getattr(exc, "details", None), dict)
            and "invalid_mode" in exc.details
        ):
            return "risk_scoring"
        return "invocation_validation"
    if isinstance(exc, PolicyLoadError):
        return "invocation_validation"
    if isinstance(exc, GuardEvaluationError):
        return "guard_evaluation"
    if isinstance(exc, ConditionResolutionError):
        return "condition_resolution"
    if isinstance(exc, AuditSinkError):
        return "sink_emission"
    if isinstance(exc, RiskThresholdError):
        return "risk_scoring"
    if isinstance(exc, ToolConstraintViolationError):
        return "tool_validation"
    if isinstance(exc, PreconditionError):
        return "precondition_validation"
    if isinstance(exc, SchemaValidationError):
        return "schema_validation"
    if isinstance(exc, CustomGateViolationError):
        return "custom_gate_violation"
    if isinstance(exc, GovernanceViolationError):
        if "role" in str(exc).lower():
            return "role_validation"
        return "postcondition_validation"
    return "invocation_validation"


def _make_custom_gate_runner(
    grouped_gates: dict[str, list[EnforcementGate]],
    invocation: Mapping[str, Any],
    gates_evaluated: list[str],
    all_custom_metadata: dict[str, Any],
):
    """Create a closure that runs custom gates at a given insertion point.

    Returns a callable ``(insertion_point, policy_view) -> None`` that
    raises CustomGateViolationError on failure.
    """

    def _run_custom_gates_at(
        insertion_point: str,
        policy_view: dict[str, Any],
    ) -> None:
        gates_at = grouped_gates.get(insertion_point, [])
        if not gates_at:
            return
        failures, meta = run_gates(
            gates_at, invocation, policy_view, {},
            gates_evaluated, [],
        )
        if meta:
            all_custom_metadata.update(meta)
        if failures:
            raise CustomGateViolationError(
                f"Custom gate failed at {insertion_point}: "
                f"{failures[0].get('message', 'unknown')}",
                details={
                    "custom_gate_failures": failures,
                    "insertion_point": insertion_point,
                },
            )

    return _run_custom_gates_at


def _build_phase_a_mid_pipeline_fail_artifact(
    invocation_without_output: Mapping[str, Any],
    policy: dict[str, Any],
    exc: AIGCError,
    phase_a_gates: list[str],
    redaction_patterns: list[tuple[str, re.Pattern[str]]] | None = None,
) -> dict[str, Any]:
    """Build and return the FAIL artifact for a mid-pipeline Phase A failure.

    Does NOT emit to sink or attach the artifact to exc — the caller is
    responsible for both.

    :param invocation_without_output: Invocation dict (output will be {})
    :param policy: Loaded policy dict
    :param exc: The AIGCError that caused the failure
    :param phase_a_gates: Gates evaluated before the failure
    :param redaction_patterns: Optional patterns for failure message sanitization
    :return: FAIL audit artifact dict
    """
    safe_inv = dict(invocation_without_output)
    safe_inv["output"] = {}

    failure_gate = _map_exception_to_failure_gate(exc)
    raw_reason = str(exc)
    failure_reason, reason_redacted = sanitize_failure_message(
        raw_reason, redaction_patterns,
    )
    redacted_fields: list[str] = list(reason_redacted)
    failures = None
    if hasattr(exc, "details") and exc.details:
        sanitized_msg, msg_redacted = sanitize_failure_message(
            str(exc), redaction_patterns,
        )
        for r in msg_redacted:
            if r not in redacted_fields:
                redacted_fields.append(r)
        failures = [
            {
                "code": exc.__class__.__name__,
                "message": sanitized_msg,
                "field": (
                    exc.details.get("field")
                    if isinstance(exc.details, dict)
                    else None
                ),
            }
        ]

    fail_metadata: dict[str, Any] = {
        "enforcement_mode": "split_pre_call_only",
        "pre_call_gates_evaluated": list(phase_a_gates),
        "redacted_fields": redacted_fields,
    }

    return generate_audit_artifact(
        safe_inv,
        policy,
        enforcement_result="FAIL",
        failures=failures,
        failure_gate=failure_gate,
        failure_reason=failure_reason,
        metadata=fail_metadata,
    )


def _run_phase_a(
    policy: dict[str, Any],
    invocation: Mapping[str, Any],
    *,
    custom_gates: list[EnforcementGate] | None = None,
    grouped_gates: dict[str, list[EnforcementGate]] | None = None,
    span: Any = None,
    gates_evaluated: list[str] | None = None,
) -> tuple[
    dict[str, Any],         # effective_policy
    list[dict[str, Any]],   # guards_evaluated (from guard engine)
    dict[str, Any],         # conditions_resolved
    dict[str, Any],         # all_custom_metadata
    list[str],              # gates_evaluated (pipeline gate list)
    dict[str, Any],         # phase_a_extra (preconditions, tools, etc.)
]:
    """Execute Phase A enforcement (pre-call gates).

    Runs gates 1-7: pre_auth custom gates, guard evaluation, role validation,
    precondition validation, tool constraint validation, post_auth custom gates.

    The caller may pass a mutable ``gates_evaluated`` list; on exception the
    caller can inspect the partial progress that was recorded before the
    failure.

    Returns: (effective_policy, guards_evaluated_from_engine,
              conditions_resolved, all_custom_metadata,
              gates_evaluated_list, phase_a_extra)
    """
    # ── PIPELINE_CONTRACT ────────────────────────────────────────
    # Do not reorder authorization gates after output gates.
    # Authorization: guard_evaluation -> role_validation ->
    #                precondition_validation -> tool_constraint_validation
    # Output:        schema_validation -> postcondition_validation
    # Enforced by:   tests/test_pre_action_boundary.py
    # ─────────────────────────────────────────────────────────────

    if gates_evaluated is None:
        gates_evaluated = []
    if grouped_gates is None:
        grouped_gates = sort_gates(custom_gates or [])

    all_custom_metadata: dict[str, Any] = {}
    _run_custom_gates_at = _make_custom_gate_runner(
        grouped_gates, invocation, gates_evaluated, all_custom_metadata,
    )

    # ── Pre-authorization custom gates ──────────────
    _run_custom_gates_at(INSERTION_PRE_AUTHORIZATION, policy)

    effective_policy = policy
    guards_evaluated_engine: list[dict[str, Any]] = []
    conditions_resolved: dict[str, Any] = {}
    if policy.get("guards") or policy.get("conditions"):
        logger.debug(
            "Evaluating guards and conditions for policy %s",
            invocation.get("policy_file"),
        )
        effective_policy, guards_evaluated_engine, conditions_resolved = (
            evaluate_guards(policy, invocation["context"], invocation)
        )
    _record_gate(gates_evaluated, GATE_GUARDS)
    record_gate_event(span, GATE_GUARDS)
    logger.debug(
        "Guards evaluated: %d results", len(guards_evaluated_engine),
    )

    validate_role(invocation["role"], effective_policy)
    _record_gate(gates_evaluated, GATE_ROLE)
    record_gate_event(span, GATE_ROLE)
    logger.debug("Role validated: %s", invocation["role"])

    preconditions_satisfied = validate_preconditions(
        invocation["context"], effective_policy,
    )
    _record_gate(gates_evaluated, GATE_PRECONDS)
    record_gate_event(span, GATE_PRECONDS)
    logger.debug("Preconditions satisfied: %s", preconditions_satisfied)

    tool_validation_result = validate_tool_constraints(
        invocation, effective_policy,
    )
    _record_gate(gates_evaluated, GATE_TOOLS)
    record_gate_event(span, GATE_TOOLS)
    logger.debug("Tool constraints validated")

    # ── Post-authorization custom gates ─────────────
    _run_custom_gates_at(INSERTION_POST_AUTHORIZATION, effective_policy)

    phase_a_extra = {
        "preconditions_satisfied": preconditions_satisfied,
        "tool_constraints": tool_validation_result,
    }

    return (
        effective_policy,
        guards_evaluated_engine,
        conditions_resolved,
        all_custom_metadata,
        gates_evaluated,
        phase_a_extra,
    )


def _run_phase_b(
    effective_policy: dict[str, Any],
    policy: dict[str, Any],
    invocation: Mapping[str, Any],
    *,
    phase_a_gates: list[str],
    phase_a_metadata: dict[str, Any],
    phase_a_extra: dict[str, Any],
    guards_evaluated_engine: list[dict[str, Any]],
    conditions_resolved: dict[str, Any],
    all_custom_metadata: dict[str, Any],
    grouped_gates: dict[str, list[EnforcementGate]] | None = None,
    sink: Any = None,
    sink_failure_mode: str | None = None,
    redaction_patterns: list[tuple[str, re.Pattern[str]]] | None = None,
    signer: ArtifactSigner | None = None,
    risk_config: dict[str, Any] | None = None,
    enforcement_mode: str = "unified",
    pre_call_timestamp: int | None = None,
    span: Any = None,
) -> dict[str, Any]:
    """Execute Phase B enforcement (post-call gates + artifact emission).

    Runs gates 8-13: pre_output custom gates, schema validation,
    postcondition validation, post_output custom gates, risk scoring,
    audit artifact generation.

    Returns: PASS audit artifact
    Raises: AIGCError on FAIL (with artifact attached)
    """
    _sink_kw: dict[str, Any] = {}
    if sink is not None:
        _sink_kw["sink"] = sink
    if sink_failure_mode is not None:
        _sink_kw["failure_mode"] = sink_failure_mode

    if grouped_gates is None:
        grouped_gates = sort_gates([])

    # Phase B has its own gates_evaluated list; will be merged or
    # separated in the metadata depending on enforcement_mode.
    phase_b_gates: list[str] = []

    # Build the custom gate runner for Phase B using phase_b_gates
    phase_b_custom_metadata: dict[str, Any] = {}
    _run_custom_gates_at = _make_custom_gate_runner(
        grouped_gates, invocation, phase_b_gates, phase_b_custom_metadata,
    )

    try:
        # ── Pre-output custom gates ─────────────────────
        _run_custom_gates_at(INSERTION_PRE_OUTPUT, effective_policy)

        schema_validation = "skipped"
        schema_valid = False
        if "output_schema" in effective_policy:
            validate_schema(
                invocation["output"], effective_policy["output_schema"],
            )
            schema_validation = "passed"
            schema_valid = True
            logger.debug("Output schema validation passed")
        _record_gate(phase_b_gates, GATE_SCHEMA)
        record_gate_event(span, GATE_SCHEMA)

        postconditions_satisfied = validate_postconditions(
            effective_policy,
            schema_valid=schema_valid,
        )
        _record_gate(phase_b_gates, GATE_POSTCONDS)
        record_gate_event(span, GATE_POSTCONDS)
        logger.debug(
            "Postconditions satisfied: %s", postconditions_satisfied,
        )

        # ── Post-output custom gates ────────────────────
        _run_custom_gates_at(INSERTION_POST_OUTPUT, effective_policy)

        # ── Risk scoring ────────────────────────────────
        risk_result: RiskScore | None = None
        effective_risk_config = risk_config or policy.get("risk")
        if effective_risk_config:
            risk_result = compute_risk_score(
                invocation, effective_policy,
                risk_config=effective_risk_config,
            )
            _record_gate(phase_b_gates, GATE_RISK)
            record_gate_event(
                span, GATE_RISK,
                details={"score": risk_result.score},
            )

            if risk_result.exceeded:
                if risk_result.mode == RISK_MODE_STRICT:
                    raise RiskThresholdError(
                        f"Risk score {risk_result.score:.3f} exceeds "
                        f"threshold {risk_result.threshold:.3f} "
                        f"in strict mode",
                        details=risk_result.to_dict(),
                    )
                elif risk_result.mode == RISK_MODE_WARN_ONLY:
                    logger.warning(
                        "Risk score %.3f exceeds threshold %.3f "
                        "(warn_only mode -- not blocking)",
                        risk_result.score,
                        risk_result.threshold,
                    )

        # Merge custom metadata from Phase A and Phase B
        merged_custom_metadata = dict(all_custom_metadata)
        if phase_b_custom_metadata:
            merged_custom_metadata.update(phase_b_custom_metadata)

        # Build metadata based on enforcement_mode
        if enforcement_mode == "unified":
            combined_gates = list(phase_a_gates) + list(phase_b_gates)
            metadata: dict[str, Any] = {
                "preconditions_satisfied": phase_a_extra.get(
                    "preconditions_satisfied", [],
                ),
                "postconditions_satisfied": postconditions_satisfied,
                "schema_validation": schema_validation,
                "guards_evaluated": guards_evaluated_engine,
                "conditions_resolved": conditions_resolved,
                "tool_constraints": phase_a_extra.get(
                    "tool_constraints", {},
                ),
                "gates_evaluated": combined_gates,
                "enforcement_mode": "unified",
            }
        else:
            # split mode
            post_call_timestamp = int(_time.time())
            metadata = {
                "preconditions_satisfied": phase_a_extra.get(
                    "preconditions_satisfied", [],
                ),
                "postconditions_satisfied": postconditions_satisfied,
                "schema_validation": schema_validation,
                "guards_evaluated": guards_evaluated_engine,
                "conditions_resolved": conditions_resolved,
                "tool_constraints": phase_a_extra.get(
                    "tool_constraints", {},
                ),
                "enforcement_mode": "split",
                "pre_call_gates_evaluated": list(phase_a_gates),
                "post_call_gates_evaluated": list(phase_b_gates),
                "pre_call_timestamp": pre_call_timestamp,
                "post_call_timestamp": post_call_timestamp,
            }

        if merged_custom_metadata:
            metadata["custom_gate_metadata"] = dict(
                sorted(merged_custom_metadata.items()),
            )

        if risk_result is not None:
            metadata["risk_scoring"] = risk_result.to_dict()

        audit_record = generate_audit_artifact(
            invocation,
            policy,
            enforcement_result="PASS",
            metadata=metadata,
            risk_score=(
                risk_result.score if risk_result is not None else None
            ),
        )

        # Sign artifact if signer is configured
        if signer is not None:
            sign_artifact(audit_record, signer)

        emit_to_sink(audit_record, **_sink_kw)
        record_enforcement_result(
            span, "PASS",
            policy_file=invocation.get("policy_file"),
            role=invocation.get("role"),
            risk_score=(
                risk_result.score if risk_result is not None else None
            ),
            enforcement_mode=enforcement_mode,
        )
        logger.info(
            "Enforcement complete: PASS [policy=%s, role=%s]",
            invocation.get("policy_file"),
            invocation.get("role"),
        )
        return audit_record

    except AIGCError as exc:
        # Build combined gates list for FAIL artifact metadata
        if enforcement_mode == "unified":
            all_gates = list(phase_a_gates) + list(phase_b_gates)
        else:
            all_gates = list(phase_b_gates)

        failure_gate = _map_exception_to_failure_gate(exc)
        raw_reason = str(exc)
        failure_reason, reason_redacted = sanitize_failure_message(
            raw_reason, redaction_patterns,
        )

        redacted_fields: list[str] = list(reason_redacted)
        failures = None
        if hasattr(exc, "details") and exc.details:
            sanitized_msg, msg_redacted = sanitize_failure_message(
                str(exc), redaction_patterns,
            )
            for r in msg_redacted:
                if r not in redacted_fields:
                    redacted_fields.append(r)
            failures = [
                {
                    "code": exc.__class__.__name__,
                    "message": sanitized_msg,
                    "field": (
                        exc.details.get("field")
                        if isinstance(exc.details, dict)
                        else None
                    ),
                }
            ]

        if enforcement_mode == "unified":
            fail_metadata: dict[str, Any] = {
                "gates_evaluated": all_gates,
                "redacted_fields": redacted_fields,
                "enforcement_mode": "unified",
            }
        else:
            post_call_timestamp = int(_time.time())
            fail_metadata = {
                "enforcement_mode": "split",
                "pre_call_gates_evaluated": list(phase_a_gates),
                "post_call_gates_evaluated": all_gates,
                "pre_call_timestamp": pre_call_timestamp,
                "post_call_timestamp": post_call_timestamp,
                "redacted_fields": redacted_fields,
            }

        if isinstance(exc, RiskThresholdError) and isinstance(
            getattr(exc, "details", None), dict,
        ):
            fail_metadata["risk_scoring"] = exc.details

        audit_record = generate_audit_artifact(
            invocation,
            policy,
            enforcement_result="FAIL",
            failures=failures,
            failure_gate=failure_gate,
            failure_reason=failure_reason,
            metadata=fail_metadata,
        )

        # Sign FAIL artifacts too
        if signer is not None:
            sign_artifact(audit_record, signer)

        exc.audit_artifact = audit_record
        try:
            emit_to_sink(audit_record, **_sink_kw)
        except AuditSinkError as sink_exc:
            # Log sink failure but never let it replace the governance
            # exception.  The audit artifact is already attached to exc;
            # evidence must not be lost even when the sink is in
            # "raise" mode.
            logger.error(
                "Sink emission failed on FAIL path "
                "(artifact preserved): %s",
                sink_exc,
            )
        record_enforcement_result(
            span, "FAIL",
            policy_file=invocation.get("policy_file"),
            role=invocation.get("role"),
            enforcement_mode=enforcement_mode,
        )
        logger.error(
            "Enforcement failed at gate '%s': %s",
            failure_gate,
            failure_reason,
        )
        logger.info(
            "Enforcement complete: FAIL [gate=%s, policy=%s, role=%s]",
            failure_gate,
            invocation.get("policy_file"),
            invocation.get("role"),
        )
        raise


def _run_pipeline(
    policy: dict[str, Any],
    invocation: Mapping[str, Any],
    *,
    sink: Any = None,
    sink_failure_mode: str | None = None,
    redaction_patterns: list[tuple[str, re.Pattern[str]]] | None = None,
    signer: ArtifactSigner | None = None,
    custom_gates: list[EnforcementGate] | None = None,
    risk_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run the enforcement pipeline against a pre-loaded policy.

    Shared by enforce_invocation (sync) and enforce_invocation_async (async).
    Generates and emits an audit artifact on both PASS and FAIL.

    :param policy: Pre-loaded and validated policy dict
    :param invocation: Validated invocation dict
    :param sink: Explicit sink to use (None = use global default via sentinel)
    :param sink_failure_mode: Explicit failure mode (None = use global default)
    :param redaction_patterns: Patterns for failure message sanitization
    :param signer: Optional artifact signer
    :param custom_gates: Optional custom enforcement gates
    :param risk_config: Optional risk scoring configuration override
    :return: PASS audit artifact
    :raises: AIGCError subclasses on governance violation (FAIL audit emitted first)
    """
    _sink_kw: dict[str, Any] = {}
    if sink is not None:
        _sink_kw["sink"] = sink
    if sink_failure_mode is not None:
        _sink_kw["failure_mode"] = sink_failure_mode

    grouped_gates = sort_gates(custom_gates or [])

    with enforcement_span(
        "aigc.enforce_invocation",
        attributes={
            "aigc.policy_file": invocation.get("policy_file", ""),
            "aigc.role": invocation.get("role", ""),
        },
    ) as span:
        # Phase A may raise AIGCError; we catch it to generate the FAIL
        # artifact (same as the old monolithic try/except).
        # Pass a mutable list so we can read partial progress on failure.
        phase_a_gates: list[str] = []
        try:
            (
                effective_policy,
                guards_evaluated_engine,
                conditions_resolved,
                all_custom_metadata,
                phase_a_gates,
                phase_a_extra,
            ) = _run_phase_a(
                policy, invocation,
                grouped_gates=grouped_gates,
                span=span,
                gates_evaluated=phase_a_gates,
            )
        except AIGCError as exc:
            # Phase A failure in unified mode -- generate FAIL artifact
            # with the gates that were evaluated before the failure.
            failure_gate = _map_exception_to_failure_gate(exc)
            raw_reason = str(exc)
            failure_reason, reason_redacted = sanitize_failure_message(
                raw_reason, redaction_patterns,
            )
            redacted_fields: list[str] = list(reason_redacted)
            failures = None
            if hasattr(exc, "details") and exc.details:
                sanitized_msg, msg_redacted = sanitize_failure_message(
                    str(exc), redaction_patterns,
                )
                for r in msg_redacted:
                    if r not in redacted_fields:
                        redacted_fields.append(r)
                failures = [
                    {
                        "code": exc.__class__.__name__,
                        "message": sanitized_msg,
                        "field": (
                            exc.details.get("field")
                            if isinstance(exc.details, dict)
                            else None
                        ),
                    }
                ]

            fail_metadata: dict[str, Any] = {
                "gates_evaluated": list(phase_a_gates),
                "redacted_fields": redacted_fields,
                "enforcement_mode": "unified",
            }
            if isinstance(exc, RiskThresholdError) and isinstance(
                getattr(exc, "details", None), dict,
            ):
                fail_metadata["risk_scoring"] = exc.details

            audit_record = generate_audit_artifact(
                invocation,
                policy,
                enforcement_result="FAIL",
                failures=failures,
                failure_gate=failure_gate,
                failure_reason=failure_reason,
                metadata=fail_metadata,
            )
            if signer is not None:
                sign_artifact(audit_record, signer)
            exc.audit_artifact = audit_record
            try:
                emit_to_sink(audit_record, **_sink_kw)
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on FAIL path "
                    "(artifact preserved): %s",
                    sink_exc,
                )
            record_enforcement_result(
                span, "FAIL",
                policy_file=invocation.get("policy_file"),
                role=invocation.get("role"),
                enforcement_mode="unified",
            )
            logger.error(
                "Enforcement failed at gate '%s': %s",
                failure_gate,
                failure_reason,
            )
            logger.info(
                "Enforcement complete: FAIL [gate=%s, policy=%s, role=%s]",
                failure_gate,
                invocation.get("policy_file"),
                invocation.get("role"),
            )
            raise

        return _run_phase_b(
            effective_policy,
            policy,
            invocation,
            phase_a_gates=phase_a_gates,
            phase_a_metadata={},
            phase_a_extra=phase_a_extra,
            guards_evaluated_engine=guards_evaluated_engine,
            conditions_resolved=conditions_resolved,
            all_custom_metadata=all_custom_metadata,
            grouped_gates=grouped_gates,
            sink=sink,
            sink_failure_mode=sink_failure_mode,
            redaction_patterns=redaction_patterns,
            signer=signer,
            risk_config=risk_config,
            enforcement_mode="unified",
            span=span,
        )


def enforce_invocation(invocation: Mapping[str, Any]) -> dict[str, Any]:
    """
    Enforce all governance rules for a model invocation (synchronous).

    :param invocation: Dict with:
      - "policy_file": path to policy
      - "input": model input
      - "output": model output (to be validated)
      - "context": additional context
      - "model_provider", "model_identifier", "role": identity fields
    :return: audit artifact (PASS or FAIL)
    :raises: AIGCError subclasses on governance violation (after audit emission)
    """
    if not isinstance(invocation, Mapping):
        _exc = InvocationValidationError(
            "Invocation must be a mapping object",
            details={"received_type": type(invocation).__name__},
        )
        _safe = {
            "policy_file": "unknown", "model_provider": "unknown",
            "model_identifier": "unknown", "role": "unknown",
            "input": {}, "output": {}, "context": {},
        }
        _artifact = _generate_pre_pipeline_fail_artifact(_safe, _exc)
        _artifact.setdefault("metadata", {})["enforcement_mode"] = "unified"
        _exc.audit_artifact = _artifact
        try:
            emit_to_sink(_artifact)
        except AuditSinkError as _sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s", _sink_exc,
            )
        raise _exc

    try:
        _validate_invocation(invocation)
        policy = load_policy(invocation["policy_file"])
    except AIGCError as exc:
        artifact = _generate_pre_pipeline_fail_artifact(invocation, exc)
        # Unified entry point: stamp enforcement_mode so consumers can
        # branch consistently (Round 2 audit Finding 4, spec §11.2).
        artifact.setdefault("metadata", {})["enforcement_mode"] = "unified"
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s",
                sink_exc,
            )
        raise
    return _run_pipeline(policy, invocation)


async def enforce_invocation_async(
    invocation: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Enforce all governance rules for a model invocation (asynchronous).

    Policy file I/O runs in a thread pool via asyncio.to_thread to avoid
    blocking the event loop.  The enforcement pipeline itself is synchronous
    (CPU-bound and fast).

    Produces identical results to enforce_invocation() given the same inputs.

    :param invocation: Same shape as enforce_invocation()
    :return: audit artifact (PASS or FAIL)
    :raises: AIGCError subclasses on governance violation (after audit emission)
    """
    if not isinstance(invocation, Mapping):
        _exc = InvocationValidationError(
            "Invocation must be a mapping object",
            details={"received_type": type(invocation).__name__},
        )
        _safe = {
            "policy_file": "unknown", "model_provider": "unknown",
            "model_identifier": "unknown", "role": "unknown",
            "input": {}, "output": {}, "context": {},
        }
        _artifact = _generate_pre_pipeline_fail_artifact(_safe, _exc)
        _artifact.setdefault("metadata", {})["enforcement_mode"] = "unified"
        _exc.audit_artifact = _artifact
        try:
            emit_to_sink(_artifact)
        except AuditSinkError as _sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s", _sink_exc,
            )
        raise _exc

    try:
        _validate_invocation(invocation)
        policy = await asyncio.to_thread(
            load_policy, invocation["policy_file"]
        )
    except AIGCError as exc:
        artifact = _generate_pre_pipeline_fail_artifact(invocation, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = "unified"
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s",
                sink_exc,
            )
        raise
    return _run_pipeline(policy, invocation)


def enforce_pre_call(
    invocation: Mapping[str, Any],
    *,
    custom_gates: list[EnforcementGate] | None = None,
) -> PreCallResult:
    """Enforce pre-call governance checks (Phase A).

    Accepts an invocation dict WITHOUT 'output'. Runs all pre-call gates:
    custom pre_authorization gates, guard evaluation, role validation,
    precondition validation, tool constraint validation, post_authorization
    gates.

    :param invocation: Dict with policy_file, model_provider,
                       model_identifier, role, input, context
                       (no output required)
    :param custom_gates: Optional custom enforcement gates
    :return: PreCallResult token for use with enforce_post_call()
    :raises: AIGCError subclasses on governance violation
             (FAIL artifact emitted)
    """
    if not isinstance(invocation, Mapping):
        _exc = InvocationValidationError(
            "Invocation must be a mapping object",
            details={"received_type": type(invocation).__name__},
        )
        _safe = {
            "policy_file": "unknown", "model_provider": "unknown",
            "model_identifier": "unknown", "role": "unknown",
            "input": {}, "output": {}, "context": {},
        }
        _artifact = _generate_pre_pipeline_fail_artifact(_safe, _exc)
        _artifact.setdefault("metadata", {})["enforcement_mode"] = (
            "split_pre_call_only"
        )
        _exc.audit_artifact = _artifact
        try:
            emit_to_sink(_artifact)
        except AuditSinkError as _sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s", _sink_exc,
            )
        raise _exc

    try:
        _validate_pre_call_invocation(invocation)
        policy = load_policy(invocation["policy_file"])
    except AIGCError as exc:
        # Generate pre-pipeline fail artifact for split mode.
        # output is {} (no output in pre-call).
        safe_inv = dict(invocation)
        safe_inv.setdefault("output", {})
        artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = (
            "split_pre_call_only"
        )
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s",
                sink_exc,
            )
        raise

    grouped_gates = sort_gates(custom_gates or [])
    pre_call_timestamp = int(_time.time())
    # Unique per-token nonce ensures _token_hmac is unique even for
    # identical invocations in the same second (Finding 3, 2026-04-05).
    _token_nonce = os.urandom(16).hex()

    with enforcement_span(
        "aigc.enforce_pre_call",
        attributes={
            "aigc.policy_file": invocation.get("policy_file", ""),
            "aigc.role": invocation.get("role", ""),
            "aigc.enforcement_mode": "split",
        },
    ) as span:
        phase_a_gates: list[str] = []
        try:
            (
                effective_policy,
                guards_evaluated_engine,
                conditions_resolved,
                all_custom_metadata,
                phase_a_gates,
                phase_a_extra,
            ) = _run_phase_a(
                policy, invocation,
                grouped_gates=grouped_gates,
                span=span,
                gates_evaluated=phase_a_gates,
            )
        except AIGCError as exc:
            # Mid-pipeline Phase A FAIL: generate artifact with output={}
            audit_record = _build_phase_a_mid_pipeline_fail_artifact(
                invocation, policy, exc, phase_a_gates,
            )
            exc.audit_artifact = audit_record
            try:
                emit_to_sink(audit_record)
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on FAIL path "
                    "(artifact preserved): %s",
                    sink_exc,
                )
            failure_gate = _map_exception_to_failure_gate(exc)
            failure_reason = sanitize_failure_message(str(exc), None)[0]
            record_enforcement_result(
                span, "FAIL",
                policy_file=invocation.get("policy_file"),
                role=invocation.get("role"),
                enforcement_mode="split",
            )
            logger.error(
                "Enforcement failed at gate '%s': %s",
                failure_gate,
                failure_reason,
            )
            raise

        # Build invocation snapshot (exactly 6 required fields, no output).
        # Deep-copy mutable nested fields so callers cannot tamper with
        # the stored snapshot between Phase A and Phase B (Finding 3).
        invocation_snapshot = {
            "policy_file": invocation["policy_file"],
            "model_provider": invocation["model_provider"],
            "model_identifier": invocation["model_identifier"],
            "role": invocation["role"],
            "input": copy.deepcopy(invocation["input"]),
            "context": copy.deepcopy(invocation["context"]),
        }

        phase_a_metadata = {
            "gates_evaluated": list(phase_a_gates),
            "pre_call_timestamp": pre_call_timestamp,
            **phase_a_extra,
            "all_custom_metadata": all_custom_metadata,
        }

        record_enforcement_result(
            span, "PASS_PHASE_A",
            policy_file=invocation.get("policy_file"),
            role=invocation.get("role"),
            enforcement_mode="split",
        )

        # Deep-copy effective_policy so callers cannot weaken Phase B
        # enforcement rules by mutating nested policy dicts (Finding 3).
        token = PreCallResult(
            effective_policy=copy.deepcopy(effective_policy),
            resolved_guards=tuple(
                dict(g) if isinstance(g, dict) else g
                for g in guards_evaluated_engine
            ),
            resolved_conditions=dict(conditions_resolved),
            phase_a_metadata=phase_a_metadata,
            invocation_snapshot=invocation_snapshot,
            policy_file=invocation["policy_file"],
            model_provider=invocation["model_provider"],
            model_identifier=invocation["model_identifier"],
            role=invocation["role"],
        )
        # Stamp Phase B gates, provenance marker, and frozen copies.
        # All are init=False so object.__setattr__ is required on a
        # frozen dataclass.
        # Wrap in MappingProxyType (outer) + tuples (inner) so callers
        # cannot replace or append to gate lists after Phase A PASS
        # (Round 3 audit Finding 1).
        object.__setattr__(
            token, "_phase_b_grouped_gates",
            types.MappingProxyType(
                {pt: tuple(gl) for pt, gl in grouped_gates.items()}
            ),
        )
        object.__setattr__(token, "_origin", _ENFORCEMENT_TOKEN)
        # Take a second independent deep copy of the already-copied
        # fields. Phase B reads from _frozen_* so caller mutations to
        # the public fields after Phase A do not affect enforcement.
        object.__setattr__(
            token, "_frozen_effective_policy",
            copy.deepcopy(token.effective_policy),
        )
        object.__setattr__(
            token, "_frozen_invocation_snapshot",
            copy.deepcopy(token.invocation_snapshot),
        )
        # Serialize token state to immutable bytes.  Phase B deserializes
        # fresh copies from these bytes so any caller mutation of
        # _frozen_effective_policy, _frozen_invocation_snapshot,
        # _frozen_phase_a_metadata, resolved_guards, or resolved_conditions
        # after Phase A has no effect on Phase B enforcement or artifacts
        # (Round 3 audit Findings 1 & 2).
        try:
            frozen_policy_bytes = json.dumps(
                token.effective_policy, sort_keys=True,
            ).encode()
            frozen_evidence_bytes = json.dumps(
                {
                    "invocation_snapshot": dict(token.invocation_snapshot),
                    "phase_a_metadata": phase_a_metadata,
                    "guards_evaluated_engine": [
                        dict(g) if isinstance(g, dict) else None
                        for g in guards_evaluated_engine
                    ],
                    "conditions_resolved": dict(conditions_resolved),
                    # Finding 1: policy in evidence so Phase B reads from signed bytes.
                    "effective_policy": dict(token.effective_policy),
                    # Finding 2: gate fingerprint so Phase B can verify _phase_b_grouped_gates.
                    "gate_fingerprint": _gate_fingerprint(grouped_gates),
                    # Finding 3: unique per-token nonce so _token_hmac is unique
                    # even for identical invocations within the same second.
                    "token_nonce": _token_nonce,
                },
                sort_keys=True,
            ).encode()
        except (TypeError, ValueError) as json_exc:
            freeze_err = InvocationValidationError(
                f"Policy contains non-JSON-serializable values; "
                f"cannot freeze token: {json_exc}",
                details={"field": "effective_policy"},
            )
            safe_inv = dict(invocation)
            safe_inv.setdefault("output", {})
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, freeze_err,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split_pre_call_only"
            )
            freeze_err.audit_artifact = artifact
            try:
                emit_to_sink(artifact)
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on policy freeze FAIL path: %s",
                    sink_exc,
                )
            raise freeze_err from json_exc
        object.__setattr__(token, "_frozen_policy_bytes", frozen_policy_bytes)
        object.__setattr__(token, "_frozen_evidence_bytes", frozen_evidence_bytes)
        object.__setattr__(token, "_token_hmac", _token_sign(frozen_evidence_bytes))
        # Deep-copy phase_a_metadata so Phase B artifact evidence cannot
        # be forged by mutating the public phase_a_metadata field
        # (Round 2 audit Finding 2).
        object.__setattr__(
            token, "_frozen_phase_a_metadata",
            copy.deepcopy(phase_a_metadata),
        )
        return token


def enforce_post_call(
    pre_call_result: PreCallResult,
    output: dict[str, Any],
) -> dict[str, Any]:
    """Enforce post-call governance checks (Phase B).

    Consumes a PreCallResult from enforce_pre_call() plus the model output.
    One-time use: raises InvocationValidationError on reuse.

    :param pre_call_result: Token from enforce_pre_call()
    :param output: Model output dict
    :return: PASS audit artifact
    :raises: InvocationValidationError on invalid/reused pre_call_result
             or output
    :raises: AIGCError subclasses on governance violation
             (FAIL artifact emitted)
    """
    # 1. Type check
    if not isinstance(pre_call_result, PreCallResult):
        exc = InvocationValidationError(
            "enforce_post_call() requires a PreCallResult "
            "from enforce_pre_call()",
            details={"received_type": type(pre_call_result).__name__},
        )
        safe_inv = {
            "policy_file": "unknown", "model_provider": "unknown",
            "model_identifier": "unknown", "role": "unknown",
            "input": {}, "output": {}, "context": {},
        }
        artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s", sink_exc,
            )
        raise exc

    # 1b. Provenance check — reject directly-constructed PreCallResult
    # objects (forgery prevention, Finding 2).
    if pre_call_result._origin is not _ENFORCEMENT_TOKEN:
        exc = InvocationValidationError(
            "PreCallResult was not issued by enforce_pre_call(); "
            "directly-constructed tokens are rejected",
            details={"field": "pre_call_result"},
        )
        safe_inv = {
            "policy_file": "unknown", "model_provider": "unknown",
            "model_identifier": "unknown", "role": "unknown",
            "input": {}, "output": {}, "context": {},
        }
        artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s", sink_exc,
            )
        raise exc

    # 1c. HMAC integrity check — rejects tokens where _origin was stamped via
    # object.__setattr__ without holding the session signing key (audit
    # Finding #1, 2026-04-05).  Combined with the sentinel check above this
    # provides defense-in-depth against trivial in-process token forgery.
    if not _token_verify(
        pre_call_result._frozen_evidence_bytes,
        pre_call_result._token_hmac,
    ):
        exc = InvocationValidationError(
            "PreCallResult token integrity check failed; "
            "token may be forged or corrupted",
            details={"field": "pre_call_result"},
        )
        safe_inv = {
            "policy_file": "unknown", "model_provider": "unknown",
            "model_identifier": "unknown", "role": "unknown",
            "input": {}, "output": {}, "context": {},
        }
        artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s", sink_exc,
            )
        raise exc

    # 1d. Pre-deserialize evidence for authenticated identity in error paths.
    # HMAC verified above; _frozen_evidence_bytes is now authenticated.
    # Use _verified_snap for all FAIL artifact safe_inv construction below so
    # that mutations to _frozen_invocation_snapshot do not forge artifact
    # identity (audit Finding 4, 2026-04-05).
    # If the bytes are not valid JSON the token is corrupted; raise immediately.
    try:
        _pre_verified_evidence = json.loads(
            pre_call_result._frozen_evidence_bytes
        )
        _verified_snap = dict(_pre_verified_evidence["invocation_snapshot"])
        _verified_snap.setdefault("output", {})
    except (TypeError, ValueError, KeyError) as _ev_exc:
        exc = InvocationValidationError(
            "PreCallResult contains invalid internal token state; "
            "token may be corrupted or forged",
            details={"field": "_frozen_evidence_bytes"},
        )
        safe_inv = {
            "policy_file": "unknown", "model_provider": "unknown",
            "model_identifier": "unknown", "role": "unknown",
            "input": {}, "output": {}, "context": {},
        }
        artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s", sink_exc,
            )
        raise exc from _ev_exc

    # 1e. Gate fingerprint integrity check — detects object.__setattr__ replacement
    # of _phase_b_grouped_gates after Phase A (audit Finding 2, 2026-04-05).
    # Skip if absent from evidence (backward compat: old pickled tokens lack this key).
    _expected_gate_fp = _pre_verified_evidence.get("gate_fingerprint")
    if _expected_gate_fp is not None:
        _actual_gate_fp = _gate_fingerprint(pre_call_result._phase_b_grouped_gates)
        if _actual_gate_fp != _expected_gate_fp:
            exc = InvocationValidationError(
                "Phase B gate manifest was tampered; "
                "gate fingerprint does not match signed evidence",
                details={"field": "_phase_b_grouped_gates"},
            )
            safe_inv = dict(_verified_snap)
            artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
            artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
            exc.audit_artifact = artifact
            try:
                emit_to_sink(artifact)
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on gate fingerprint FAIL path: %s", sink_exc,
                )
            raise exc

    # 1f. Clone replay check — rejects second consumption of the same logical token
    # (whether original or clone). Keyed by _token_hmac (unique per session + content).
    # audit Finding 3, 2026-04-05.
    if pre_call_result._token_hmac in _consumed_token_registry:
        exc = InvocationValidationError(
            "Token replay attempt detected; this token or a clone "
            "of it has already been consumed",
            details={"field": "pre_call_result"},
        )
        safe_inv = dict(_verified_snap)
        artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on clone replay FAIL path: %s", sink_exc,
            )
        raise exc

    # 2. Output type validation
    if not isinstance(output, dict):
        exc = InvocationValidationError(
            "enforce_post_call() output must be a dict",
            details={"field": "output"},
        )
        safe_inv = dict(_verified_snap)
        artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s", sink_exc,
            )
        raise exc

    # 2b. Output serializability check (Finding 4).
    # Mirror _validate_invocation()'s json.dumps() check so that a
    # non-serializable output produces a typed FAIL artifact rather
    # than a raw TypeError escaping from checksum generation later.
    # Must happen BEFORE _consumed is flipped.
    try:
        json.dumps(output, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as json_exc:
        exc = InvocationValidationError(
            f"enforce_post_call() output is not JSON-serializable: "
            f"{json_exc}",
            details={"field": "output"},
        )
        safe_inv = dict(_verified_snap)
        artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s",
                sink_exc,
            )
        raise exc from json_exc

    # 3. Consumption check
    if pre_call_result._consumed:
        exc = InvocationValidationError(
            "PreCallResult has already been consumed; "
            "create a new one via enforce_pre_call()",
            details={"field": "pre_call_result"},
        )
        safe_inv = dict(_verified_snap)
        artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s", sink_exc,
            )
        raise exc

    # 4. Use pre-deserialized evidence from step 1d; read policy from
    # authenticated evidence (Finding 1, 2026-04-05).
    # _frozen_policy_bytes may have been replaced; evidence bytes are HMAC-verified.
    # Fallback to _frozen_policy_bytes only for backward compat (old pickled tokens).
    evidence = _pre_verified_evidence
    original_policy = evidence.get("effective_policy")
    if original_policy is None:
        try:
            original_policy = json.loads(pre_call_result._frozen_policy_bytes)
        except (TypeError, ValueError):
            original_policy = {}

    # 5. Register in replay registry BEFORE marking _consumed — order matters:
    # registry add must happen first so that a concurrent clone cannot sneak through
    # the step 1f check in the window between registration and consumed-flag flip.
    # (audit Finding 3, 2026-04-05)
    _consumed_token_registry.add(pre_call_result._token_hmac)
    object.__setattr__(pre_call_result, "_consumed", True)

    full_invocation = dict(evidence["invocation_snapshot"])
    full_invocation["output"] = output

    # 6. Recover Phase A state exclusively from the evidence snapshot.
    phase_a_meta = dict(evidence["phase_a_metadata"])
    phase_a_gates = list(
        phase_a_meta.get("gates_evaluated", []),
    )
    all_custom_metadata = dict(
        phase_a_meta.get("all_custom_metadata", {}),
    )

    with enforcement_span(
        "aigc.enforce_post_call",
        attributes={
            "aigc.policy_file": pre_call_result.policy_file,
            "aigc.role": pre_call_result.role,
            "aigc.enforcement_mode": "split",
        },
    ) as span:
        return _run_phase_b(
            original_policy,
            original_policy,
            full_invocation,
            phase_a_gates=phase_a_gates,
            phase_a_metadata=phase_a_meta,
            phase_a_extra={
                "preconditions_satisfied": phase_a_meta.get(
                    "preconditions_satisfied", [],
                ),
                "tool_constraints": phase_a_meta.get(
                    "tool_constraints", {},
                ),
            },
            guards_evaluated_engine=list(
                evidence.get("guards_evaluated_engine", []),
            ),
            conditions_resolved=dict(
                evidence.get("conditions_resolved", {}),
            ),
            all_custom_metadata=all_custom_metadata,
            # Pass Phase B custom gates preserved from Phase A (Finding 1).
            grouped_gates=pre_call_result._phase_b_grouped_gates,
            enforcement_mode="split",
            pre_call_timestamp=phase_a_meta.get("pre_call_timestamp"),
            span=span,
        )


async def enforce_pre_call_async(
    invocation: Mapping[str, Any],
    *,
    custom_gates: list[EnforcementGate] | None = None,
) -> PreCallResult:
    """Async equivalent of enforce_pre_call().

    Policy file I/O runs in a thread pool via asyncio.to_thread.
    """
    if not isinstance(invocation, Mapping):
        _exc = InvocationValidationError(
            "Invocation must be a mapping object",
            details={"received_type": type(invocation).__name__},
        )
        _safe = {
            "policy_file": "unknown", "model_provider": "unknown",
            "model_identifier": "unknown", "role": "unknown",
            "input": {}, "output": {}, "context": {},
        }
        _artifact = _generate_pre_pipeline_fail_artifact(_safe, _exc)
        _artifact.setdefault("metadata", {})["enforcement_mode"] = (
            "split_pre_call_only"
        )
        _exc.audit_artifact = _artifact
        try:
            emit_to_sink(_artifact)
        except AuditSinkError as _sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s", _sink_exc,
            )
        raise _exc

    try:
        _validate_pre_call_invocation(invocation)
        policy = await asyncio.to_thread(
            load_policy, invocation["policy_file"],
        )
    except AIGCError as exc:
        safe_inv = dict(invocation)
        safe_inv.setdefault("output", {})
        artifact = _generate_pre_pipeline_fail_artifact(safe_inv, exc)
        artifact.setdefault("metadata", {})["enforcement_mode"] = (
            "split_pre_call_only"
        )
        exc.audit_artifact = artifact
        try:
            emit_to_sink(artifact)
        except AuditSinkError as sink_exc:
            logger.error(
                "Sink emission failed on pre-pipeline FAIL path: %s",
                sink_exc,
            )
        raise

    # The enforcement pipeline itself is synchronous (CPU-bound).
    # We loaded the policy async above; now run the rest synchronously.
    grouped_gates = sort_gates(custom_gates or [])
    pre_call_timestamp = int(_time.time())
    # Unique per-token nonce ensures _token_hmac is unique even for
    # identical invocations in the same second (Finding 3, 2026-04-05).
    _token_nonce = os.urandom(16).hex()

    with enforcement_span(
        "aigc.enforce_pre_call",
        attributes={
            "aigc.policy_file": invocation.get("policy_file", ""),
            "aigc.role": invocation.get("role", ""),
            "aigc.enforcement_mode": "split",
        },
    ) as span:
        phase_a_gates: list[str] = []
        try:
            (
                effective_policy,
                guards_evaluated_engine,
                conditions_resolved,
                all_custom_metadata,
                phase_a_gates,
                phase_a_extra,
            ) = _run_phase_a(
                policy, invocation,
                grouped_gates=grouped_gates,
                span=span,
                gates_evaluated=phase_a_gates,
            )
        except AIGCError as exc:
            # Mid-pipeline Phase A FAIL: generate artifact with output={}
            audit_record = _build_phase_a_mid_pipeline_fail_artifact(
                invocation, policy, exc, phase_a_gates,
            )
            exc.audit_artifact = audit_record
            try:
                emit_to_sink(audit_record)
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on FAIL path "
                    "(artifact preserved): %s",
                    sink_exc,
                )
            failure_gate = _map_exception_to_failure_gate(exc)
            failure_reason = sanitize_failure_message(str(exc), None)[0]
            record_enforcement_result(
                span, "FAIL",
                policy_file=invocation.get("policy_file"),
                role=invocation.get("role"),
                enforcement_mode="split",
            )
            logger.error(
                "Enforcement failed at gate '%s': %s",
                failure_gate,
                failure_reason,
            )
            raise

        invocation_snapshot = {
            "policy_file": invocation["policy_file"],
            "model_provider": invocation["model_provider"],
            "model_identifier": invocation["model_identifier"],
            "role": invocation["role"],
            "input": copy.deepcopy(invocation["input"]),
            "context": copy.deepcopy(invocation["context"]),
        }

        phase_a_metadata = {
            "gates_evaluated": list(phase_a_gates),
            "pre_call_timestamp": pre_call_timestamp,
            **phase_a_extra,
            "all_custom_metadata": all_custom_metadata,
        }

        record_enforcement_result(
            span, "PASS_PHASE_A",
            policy_file=invocation.get("policy_file"),
            role=invocation.get("role"),
            enforcement_mode="split",
        )

        token = PreCallResult(
            effective_policy=copy.deepcopy(effective_policy),
            resolved_guards=tuple(
                dict(g) if isinstance(g, dict) else g
                for g in guards_evaluated_engine
            ),
            resolved_conditions=dict(conditions_resolved),
            phase_a_metadata=phase_a_metadata,
            invocation_snapshot=invocation_snapshot,
            policy_file=invocation["policy_file"],
            model_provider=invocation["model_provider"],
            model_identifier=invocation["model_identifier"],
            role=invocation["role"],
        )
        object.__setattr__(
            token, "_phase_b_grouped_gates",
            types.MappingProxyType(
                {pt: tuple(gl) for pt, gl in grouped_gates.items()}
            ),
        )
        object.__setattr__(token, "_origin", _ENFORCEMENT_TOKEN)
        object.__setattr__(
            token, "_frozen_effective_policy",
            copy.deepcopy(token.effective_policy),
        )
        object.__setattr__(
            token, "_frozen_invocation_snapshot",
            copy.deepcopy(token.invocation_snapshot),
        )
        try:
            frozen_policy_bytes = json.dumps(
                token.effective_policy, sort_keys=True,
            ).encode()
            frozen_evidence_bytes = json.dumps(
                {
                    "invocation_snapshot": dict(token.invocation_snapshot),
                    "phase_a_metadata": phase_a_metadata,
                    "guards_evaluated_engine": [
                        dict(g) if isinstance(g, dict) else None
                        for g in guards_evaluated_engine
                    ],
                    "conditions_resolved": dict(conditions_resolved),
                    # Finding 1: policy in evidence so Phase B reads from signed bytes.
                    "effective_policy": dict(token.effective_policy),
                    # Finding 2: gate fingerprint so Phase B can verify _phase_b_grouped_gates.
                    "gate_fingerprint": _gate_fingerprint(grouped_gates),
                    # Finding 3: unique per-token nonce so _token_hmac is unique
                    # even for identical invocations within the same second.
                    "token_nonce": _token_nonce,
                },
                sort_keys=True,
            ).encode()
        except (TypeError, ValueError) as json_exc:
            freeze_err = InvocationValidationError(
                f"Policy contains non-JSON-serializable values; "
                f"cannot freeze token: {json_exc}",
                details={"field": "effective_policy"},
            )
            safe_inv = dict(invocation)
            safe_inv.setdefault("output", {})
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, freeze_err,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split_pre_call_only"
            )
            freeze_err.audit_artifact = artifact
            try:
                emit_to_sink(artifact)
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on policy freeze FAIL path: %s",
                    sink_exc,
                )
            raise freeze_err from json_exc
        object.__setattr__(token, "_frozen_policy_bytes", frozen_policy_bytes)
        object.__setattr__(token, "_frozen_evidence_bytes", frozen_evidence_bytes)
        object.__setattr__(token, "_token_hmac", _token_sign(frozen_evidence_bytes))
        object.__setattr__(
            token, "_frozen_phase_a_metadata",
            copy.deepcopy(phase_a_metadata),
        )
        return token


async def enforce_post_call_async(
    pre_call_result: PreCallResult,
    output: dict[str, Any],
) -> dict[str, Any]:
    """Async equivalent of enforce_post_call().

    enforce_post_call() is synchronous (CPU-bound); just call it directly.
    """
    return enforce_post_call(pre_call_result, output)


def _validate_policy_strict(policy: dict, strict_mode: bool) -> None:
    """Validate policy strictness.

    In strict mode, raises PolicyValidationError for weak policies.
    In non-strict mode, emits UserWarning for weak policies.
    """
    issues: list[str] = []

    roles = policy.get("roles")
    if not roles:
        issues.append("Policy must define non-empty 'roles' list")

    pre = policy.get("pre_conditions", {})
    required = pre.get("required")
    if not required:
        issues.append("Policy must define 'pre_conditions.required'")
    elif isinstance(required, list):
        issues.append(
            "Policy uses bare-string preconditions; "
            "strict mode requires typed (dict) preconditions"
        )

    if strict_mode:
        if issues:
            raise PolicyValidationError(
                "Strict mode policy validation failed",
                details={"issues": issues},
            )
    else:
        for issue in issues:
            warnings.warn(issue, UserWarning, stacklevel=3)


def _generate_pre_pipeline_fail_artifact(
    invocation: Mapping[str, Any],
    exc: AIGCError,
    *,
    redaction_patterns: list[tuple[str, re.Pattern[str]]] | None = None,
) -> dict[str, Any]:
    """Generate a schema-valid FAIL artifact for failures before _run_pipeline.

    This covers invocation validation, policy loading, and strict-mode
    validation failures that occur before the enforcement pipeline starts
    (Invariant D — every enforcement attempt must produce an artifact).
    """
    failure_gate = _map_exception_to_failure_gate(exc)
    failure_reason, reason_redacted = sanitize_failure_message(
        str(exc), redaction_patterns
    )

    # Build a minimal but valid invocation-like dict for artifact generation.
    # Pre-pipeline failures may not have a loaded policy, and field values
    # may be invalid types (the validation error may be about that), so we
    # defensively coerce to expected types.
    def _safe_str(v: Any, default: str = "unknown") -> str:
        return v if isinstance(v, str) and v else default

    def _safe_dict(v: Any) -> dict:
        if not isinstance(v, dict):
            return {}
        try:
            json.dumps(v, allow_nan=False, sort_keys=True)
            return v
        except (TypeError, ValueError):
            return {}

    safe_invocation = {
        "policy_file": _safe_str(invocation.get("policy_file")),
        "model_provider": _safe_str(invocation.get("model_provider")),
        "model_identifier": _safe_str(invocation.get("model_identifier")),
        "role": _safe_str(invocation.get("role")),
        "input": _safe_dict(invocation.get("input")),
        "output": _safe_dict(invocation.get("output")),
        "context": _safe_dict(invocation.get("context")),
    }

    failures = [
        {
            "code": exc.__class__.__name__,
            "message": failure_reason,
            "field": (
                exc.details.get("field")
                if isinstance(getattr(exc, "details", None), dict)
                else None
            ),
        }
    ]

    return generate_audit_artifact(
        safe_invocation,
        {},  # no policy loaded yet
        enforcement_result="FAIL",
        failures=failures,
        failure_gate=failure_gate,
        failure_reason=failure_reason,
        metadata={
            "gates_evaluated": [],
            "redacted_fields": list(reason_redacted),
            "pre_pipeline_failure": True,
        },
    )


def emit_split_fn_failure_artifact(
    pre_call_result: "PreCallResult",
    exc: Exception,
) -> dict[str, Any]:
    """Generate and emit a FAIL artifact when the wrapped function raises
    after Phase A PASS in split decorator mode.

    The artifact captures the Phase A invocation context (no output) and
    records the wrapped function failure for observability. The exception
    is NOT modified; callers should re-raise it unchanged.

    :param pre_call_result: Token from enforce_pre_call() (Phase A PASS)
    :param exc: Exception raised by the wrapped function
    :return: Emitted FAIL audit artifact
    """
    inv_snap = dict(pre_call_result._frozen_invocation_snapshot)
    inv_snap.setdefault("output", {})
    policy = dict(pre_call_result._frozen_effective_policy)

    failure_reason, _ = sanitize_failure_message(
        f"{type(exc).__name__}: {exc}", None,
    )
    failures = [
        {
            "code": type(exc).__name__,
            "message": failure_reason,
            "field": None,
        }
    ]

    artifact = generate_audit_artifact(
        inv_snap,
        policy,
        enforcement_result="FAIL",
        failures=failures,
        failure_gate="wrapped_function_error",
        failure_reason=failure_reason,
        metadata={
            "enforcement_mode": "split",
            "pre_call_gates_evaluated": pre_call_result.phase_a_metadata.get(
                "gates_evaluated", []
            ),
        },
    )

    try:
        emit_to_sink(artifact)
    except AuditSinkError as sink_exc:
        logger.error(
            "Sink emission failed on wrapped-function FAIL path: %s",
            sink_exc,
        )

    return artifact


class AIGC:
    """Instance-scoped AIGC configuration and enforcement entry point.

    All configuration (sink, enforcement mode, redaction patterns) is
    immutable after construction. Thread-safe: enforce() may be called
    from multiple threads concurrently without touching global state.

    Usage::

        from aigc import AIGC, JsonFileAuditSink

        aigc = AIGC(sink=JsonFileAuditSink("audit.jsonl"))
        artifact = aigc.enforce(invocation)
    """

    def __init__(
        self,
        *,
        sink: Any | None = None,
        on_sink_failure: str = "log",
        strict_mode: bool = False,
        redaction_patterns: list[tuple[str, re.Pattern[str]]] | None = None,
        signer: ArtifactSigner | None = None,
        custom_gates: list[EnforcementGate] | None = None,
        policy_loader: PolicyLoaderBase | None = None,
        risk_config: dict[str, Any] | None = None,
    ) -> None:
        """
        :param sink: AuditSink instance for artifact persistence
        :param on_sink_failure: Failure mode: "raise" or "log"
        :param strict_mode: Enable strict governance validation
        :param redaction_patterns: Custom redaction patterns
        :param signer: Artifact signer for signing audit artifacts
        :param custom_gates: Custom enforcement gates
        :param policy_loader: Custom policy loader implementation
        :param risk_config: Risk scoring configuration override
        """
        if on_sink_failure not in ("raise", "log"):
            raise ValueError(
                f"on_sink_failure must be 'raise' or 'log', "
                f"got '{on_sink_failure}'"
            )

        self._sink = sink
        self._on_sink_failure = on_sink_failure
        self._strict_mode = strict_mode
        self._redaction_patterns = (
            redaction_patterns
            if redaction_patterns is not None
            else DEFAULT_REDACTION_PATTERNS
        )
        self._signer = signer
        self._custom_gates = list(custom_gates or [])
        self._policy_loader = policy_loader
        self._risk_config = risk_config
        self._policy_cache = PolicyCache()

        # Validate custom gates at construction time
        for gate in self._custom_gates:
            validate_gate(gate)

    @property
    def sink(self) -> Any | None:
        return self._sink

    @property
    def strict_mode(self) -> bool:
        return self._strict_mode

    @property
    def on_sink_failure(self) -> str:
        return self._on_sink_failure

    @property
    def signer(self) -> ArtifactSigner | None:
        return self._signer

    @property
    def policy_cache(self) -> PolicyCache:
        """Per-instance policy cache."""
        return self._policy_cache

    def enforce(self, invocation: Mapping[str, Any]) -> dict[str, Any]:
        """Enforce governance rules (synchronous).

        Uses instance-owned sink, failure mode, and policy cache — no global
        state is mutated (Invariant B — per-instance isolation).

        :param invocation: Invocation dict with required fields
        :return: Audit artifact dict
        :raises: AIGCError subclasses on governance violation
        """
        if not isinstance(invocation, Mapping):
            _exc = InvocationValidationError(
                "Invocation must be a mapping object",
                details={"received_type": type(invocation).__name__},
            )
            _safe = {
                "policy_file": "unknown", "model_provider": "unknown",
                "model_identifier": "unknown", "role": "unknown",
                "input": {}, "output": {}, "context": {},
            }
            _artifact = _generate_pre_pipeline_fail_artifact(
                _safe, _exc,
                redaction_patterns=self._redaction_patterns,
            )
            _artifact.setdefault("metadata", {})["enforcement_mode"] = "unified"
            _exc.audit_artifact = _artifact
            try:
                emit_to_sink(
                    _artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as _sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    _sink_exc,
                )
            raise _exc

        try:
            _validate_invocation(invocation)
            policy = self._policy_cache.get_or_load(
                invocation["policy_file"],
                loader=self._policy_loader,
            )
            _validate_policy_strict(policy, self._strict_mode)
        except AIGCError as exc:
            artifact = _generate_pre_pipeline_fail_artifact(
                invocation, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "unified"
            )
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise

        return _run_pipeline(
            policy,
            invocation,
            sink=self._sink,
            sink_failure_mode=self._on_sink_failure,
            redaction_patterns=self._redaction_patterns,
            signer=self._signer,
            custom_gates=self._custom_gates,
            risk_config=self._risk_config,
        )

    def enforce_pre_call(
        self, invocation: Mapping[str, Any],
    ) -> PreCallResult:
        """Enforce pre-call governance checks (Phase A), instance-scoped.

        Uses instance-owned policy cache and configuration.
        Returns a PreCallResult for use with enforce_post_call().

        :param invocation: Dict with policy_file, model_provider,
                           model_identifier, role, input, context
        :return: PreCallResult token
        :raises: AIGCError subclasses on governance violation
        """
        if not isinstance(invocation, Mapping):
            _exc = InvocationValidationError(
                "Invocation must be a mapping object",
                details={"received_type": type(invocation).__name__},
            )
            _safe = {
                "policy_file": "unknown", "model_provider": "unknown",
                "model_identifier": "unknown", "role": "unknown",
                "input": {}, "output": {}, "context": {},
            }
            _artifact = _generate_pre_pipeline_fail_artifact(
                _safe, _exc,
                redaction_patterns=self._redaction_patterns,
            )
            _artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split_pre_call_only"
            )
            _exc.audit_artifact = _artifact
            try:
                emit_to_sink(
                    _artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as _sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    _sink_exc,
                )
            raise _exc

        try:
            _validate_pre_call_invocation(invocation)
            policy = self._policy_cache.get_or_load(
                invocation["policy_file"],
                loader=self._policy_loader,
            )
            _validate_policy_strict(policy, self._strict_mode)
        except AIGCError as exc:
            safe_inv = dict(invocation)
            safe_inv.setdefault("output", {})
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split_pre_call_only"
            )
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise

        grouped_gates = sort_gates(self._custom_gates)
        pre_call_timestamp = int(_time.time())
        # Unique per-token nonce ensures _token_hmac is unique even for
        # identical invocations in the same second (Finding 3, 2026-04-05).
        _token_nonce = os.urandom(16).hex()

        with enforcement_span(
            "aigc.enforce_pre_call",
            attributes={
                "aigc.policy_file": invocation.get("policy_file", ""),
                "aigc.role": invocation.get("role", ""),
                "aigc.enforcement_mode": "split",
            },
        ) as span:
            phase_a_gates: list[str] = []
            try:
                (
                    effective_policy,
                    guards_evaluated_engine,
                    conditions_resolved,
                    all_custom_metadata,
                    phase_a_gates,
                    phase_a_extra,
                ) = _run_phase_a(
                    policy, invocation,
                    grouped_gates=grouped_gates,
                    span=span,
                    gates_evaluated=phase_a_gates,
                )
            except AIGCError as exc:
                safe_inv = dict(invocation)
                safe_inv["output"] = {}
                audit_record = _build_phase_a_mid_pipeline_fail_artifact(
                    safe_inv, policy, exc, phase_a_gates,
                    self._redaction_patterns,
                )
                exc.audit_artifact = audit_record
                try:
                    emit_to_sink(
                        audit_record,
                        sink=self._sink,
                        failure_mode=self._on_sink_failure,
                    )
                except AuditSinkError as sink_exc:
                    logger.error(
                        "Sink emission failed on FAIL path "
                        "(artifact preserved): %s",
                        sink_exc,
                    )
                record_enforcement_result(
                    span, "FAIL",
                    policy_file=invocation.get("policy_file"),
                    role=invocation.get("role"),
                    enforcement_mode="split",
                )
                logger.error(
                    "Enforcement failed during Phase A: %s", exc,
                )
                raise

            invocation_snapshot = {
                "policy_file": invocation["policy_file"],
                "model_provider": invocation["model_provider"],
                "model_identifier": invocation["model_identifier"],
                "role": invocation["role"],
                "input": copy.deepcopy(invocation["input"]),
                "context": copy.deepcopy(invocation["context"]),
            }

            phase_a_metadata = {
                "gates_evaluated": list(phase_a_gates),
                "pre_call_timestamp": pre_call_timestamp,
                **phase_a_extra,
                "all_custom_metadata": all_custom_metadata,
            }

            record_enforcement_result(
                span, "PASS_PHASE_A",
                policy_file=invocation.get("policy_file"),
                role=invocation.get("role"),
                enforcement_mode="split",
            )

            token = PreCallResult(
                effective_policy=copy.deepcopy(effective_policy),
                resolved_guards=tuple(
                    dict(g) if isinstance(g, dict) else g
                    for g in guards_evaluated_engine
                ),
                resolved_conditions=dict(conditions_resolved),
                phase_a_metadata=phase_a_metadata,
                invocation_snapshot=invocation_snapshot,
                policy_file=invocation["policy_file"],
                model_provider=invocation["model_provider"],
                model_identifier=invocation["model_identifier"],
                role=invocation["role"],
            )
            object.__setattr__(
                token, "_phase_b_grouped_gates",
                types.MappingProxyType(
                    {pt: tuple(gl) for pt, gl in grouped_gates.items()}
                ),
            )
            object.__setattr__(token, "_origin", _ENFORCEMENT_TOKEN)
            object.__setattr__(
                token, "_frozen_effective_policy",
                copy.deepcopy(token.effective_policy),
            )
            object.__setattr__(
                token, "_frozen_invocation_snapshot",
                copy.deepcopy(token.invocation_snapshot),
            )
            try:
                frozen_policy_bytes = json.dumps(
                    token.effective_policy, sort_keys=True,
                ).encode()
                frozen_evidence_bytes = json.dumps(
                    {
                        "invocation_snapshot": dict(
                            token.invocation_snapshot,
                        ),
                        "phase_a_metadata": phase_a_metadata,
                        "guards_evaluated_engine": [
                            dict(g) if isinstance(g, dict) else None
                            for g in guards_evaluated_engine
                        ],
                        "conditions_resolved": dict(conditions_resolved),
                        # Finding 1: policy in evidence so Phase B reads from signed bytes.
                        "effective_policy": dict(token.effective_policy),
                        # Finding 2: gate fingerprint so Phase B can verify _phase_b_grouped_gates.
                        "gate_fingerprint": _gate_fingerprint(grouped_gates),
                        # Finding 3: unique per-token nonce so _token_hmac is unique
                        # even for identical invocations within the same second.
                        "token_nonce": _token_nonce,
                    },
                    sort_keys=True,
                ).encode()
            except (TypeError, ValueError) as json_exc:
                freeze_err = InvocationValidationError(
                    f"Policy contains non-JSON-serializable values; "
                    f"cannot freeze token: {json_exc}",
                    details={"field": "effective_policy"},
                )
                safe_inv = dict(invocation)
                safe_inv.setdefault("output", {})
                artifact = _generate_pre_pipeline_fail_artifact(
                    safe_inv, freeze_err,
                    redaction_patterns=self._redaction_patterns,
                )
                artifact.setdefault("metadata", {})["enforcement_mode"] = (
                    "split_pre_call_only"
                )
                freeze_err.audit_artifact = artifact
                try:
                    emit_to_sink(
                        artifact,
                        sink=self._sink,
                        failure_mode=self._on_sink_failure,
                    )
                except AuditSinkError as sink_exc:
                    logger.error(
                        "Sink emission failed on policy freeze FAIL path: %s",
                        sink_exc,
                    )
                raise freeze_err from json_exc
            object.__setattr__(
                token, "_frozen_policy_bytes", frozen_policy_bytes,
            )
            object.__setattr__(
                token, "_frozen_evidence_bytes", frozen_evidence_bytes,
            )
            object.__setattr__(
                token, "_token_hmac", _token_sign(frozen_evidence_bytes),
            )
            object.__setattr__(
                token, "_frozen_phase_a_metadata",
                copy.deepcopy(phase_a_metadata),
            )
            return token

    def enforce_post_call(
        self,
        pre_call_result: PreCallResult,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        """Enforce post-call governance checks (Phase B), instance-scoped.

        Consumes a PreCallResult from enforce_pre_call(). One-time use.

        :param pre_call_result: Token from enforce_pre_call()
        :param output: Model output dict
        :return: PASS audit artifact
        :raises: AIGCError subclasses on governance violation
        """
        # 1. Type check
        if not isinstance(pre_call_result, PreCallResult):
            exc = InvocationValidationError(
                "enforce_post_call() requires a PreCallResult "
                "from enforce_pre_call()",
                details={
                    "received_type": type(pre_call_result).__name__,
                },
            )
            safe_inv = {
                "policy_file": "unknown",
                "model_provider": "unknown",
                "model_identifier": "unknown",
                "role": "unknown",
                "input": {}, "output": {}, "context": {},
            }
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split"
            )
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise exc

        # 1b. Provenance check (Finding 2).
        if pre_call_result._origin is not _ENFORCEMENT_TOKEN:
            exc = InvocationValidationError(
                "PreCallResult was not issued by enforce_pre_call(); "
                "directly-constructed tokens are rejected",
                details={"field": "pre_call_result"},
            )
            safe_inv = {
                "policy_file": "unknown",
                "model_provider": "unknown",
                "model_identifier": "unknown",
                "role": "unknown",
                "input": {}, "output": {}, "context": {},
            }
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split"
            )
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise exc

        # 1c. HMAC integrity check — rejects tokens where _origin was stamped
        # via object.__setattr__ without holding the session signing key (audit
        # Finding #1, 2026-04-05).
        if not _token_verify(
            pre_call_result._frozen_evidence_bytes,
            pre_call_result._token_hmac,
        ):
            exc = InvocationValidationError(
                "PreCallResult token integrity check failed; "
                "token may be forged or corrupted",
                details={"field": "pre_call_result"},
            )
            safe_inv = {
                "policy_file": "unknown",
                "model_provider": "unknown",
                "model_identifier": "unknown",
                "role": "unknown",
                "input": {}, "output": {}, "context": {},
            }
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split"
            )
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise exc

        # 1d. Pre-deserialize evidence for authenticated identity in error paths.
        # HMAC verified above; _frozen_evidence_bytes is now authenticated.
        # Use _verified_snap for all FAIL artifact safe_inv construction below
        # so that mutations to _frozen_invocation_snapshot do not forge
        # artifact identity (audit Finding 4, 2026-04-05).
        # If the bytes are not valid JSON the token is corrupted; raise
        # immediately.
        try:
            _pre_verified_evidence = json.loads(
                pre_call_result._frozen_evidence_bytes
            )
            _verified_snap = dict(
                _pre_verified_evidence["invocation_snapshot"]
            )
            _verified_snap.setdefault("output", {})
        except (TypeError, ValueError, KeyError) as _ev_exc:
            exc = InvocationValidationError(
                "PreCallResult contains invalid internal token state; "
                "token may be corrupted or forged",
                details={"field": "_frozen_evidence_bytes"},
            )
            safe_inv = {
                "policy_file": "unknown",
                "model_provider": "unknown",
                "model_identifier": "unknown",
                "role": "unknown",
                "input": {}, "output": {}, "context": {},
            }
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise exc from _ev_exc

        # 1e. Gate fingerprint integrity check — detects object.__setattr__ replacement
        # of _phase_b_grouped_gates after Phase A (audit Finding 2, 2026-04-05).
        # Skip if absent from evidence (backward compat: old pickled tokens lack this key).
        _expected_gate_fp = _pre_verified_evidence.get("gate_fingerprint")
        if _expected_gate_fp is not None:
            _actual_gate_fp = _gate_fingerprint(pre_call_result._phase_b_grouped_gates)
            if _actual_gate_fp != _expected_gate_fp:
                exc = InvocationValidationError(
                    "Phase B gate manifest was tampered; "
                    "gate fingerprint does not match signed evidence",
                    details={"field": "_phase_b_grouped_gates"},
                )
                safe_inv = dict(_verified_snap)
                artifact = _generate_pre_pipeline_fail_artifact(
                    safe_inv, exc,
                    redaction_patterns=self._redaction_patterns,
                )
                artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
                exc.audit_artifact = artifact
                try:
                    emit_to_sink(artifact, sink=self._sink, failure_mode=self._on_sink_failure)
                except AuditSinkError as sink_exc:
                    logger.error(
                        "Sink emission failed on gate fingerprint FAIL path: %s", sink_exc,
                    )
                raise exc

        # 1f. Clone replay check — rejects second consumption of the same logical token
        # (whether original or clone). Keyed by _token_hmac (unique per session + content).
        # audit Finding 3, 2026-04-05.
        if pre_call_result._token_hmac in _consumed_token_registry:
            exc = InvocationValidationError(
                "Token replay attempt detected; this token or a clone "
                "of it has already been consumed",
                details={"field": "pre_call_result"},
            )
            safe_inv = dict(_verified_snap)
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = "split"
            exc.audit_artifact = artifact
            try:
                emit_to_sink(artifact, sink=self._sink, failure_mode=self._on_sink_failure)
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on clone replay FAIL path: %s", sink_exc,
                )
            raise exc

        # 2. Output type validation
        if not isinstance(output, dict):
            exc = InvocationValidationError(
                "enforce_post_call() output must be a dict",
                details={"field": "output"},
            )
            safe_inv = dict(_verified_snap)
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split"
            )
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise exc

        # 2b. Output serializability check (Finding 4).
        try:
            json.dumps(output, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as json_exc:
            exc = InvocationValidationError(
                f"enforce_post_call() output is not JSON-serializable: "
                f"{json_exc}",
                details={"field": "output"},
            )
            safe_inv = dict(_verified_snap)
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split"
            )
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise exc from json_exc

        # 3. Consumption check
        if pre_call_result._consumed:
            exc = InvocationValidationError(
                "PreCallResult has already been consumed; "
                "create a new one via enforce_pre_call()",
                details={"field": "pre_call_result"},
            )
            safe_inv = dict(_verified_snap)
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split"
            )
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise exc

        # 4. Use pre-deserialized evidence from step 1d; read policy from
        # authenticated evidence (Finding 1, 2026-04-05).
        # _frozen_policy_bytes may have been replaced; evidence bytes are HMAC-verified.
        # Fallback to _frozen_policy_bytes only for backward compat (old pickled tokens).
        evidence = _pre_verified_evidence
        original_policy = evidence.get("effective_policy")
        if original_policy is None:
            try:
                original_policy = json.loads(pre_call_result._frozen_policy_bytes)
            except (TypeError, ValueError):
                original_policy = {}

        # 5. Register in replay registry BEFORE marking _consumed — order matters:
        # registry add must happen first so that a concurrent clone cannot sneak through
        # the step 1f check in the window between registration and consumed-flag flip.
        # (audit Finding 3, 2026-04-05)
        _consumed_token_registry.add(pre_call_result._token_hmac)
        object.__setattr__(pre_call_result, "_consumed", True)

        full_invocation = dict(evidence["invocation_snapshot"])
        full_invocation["output"] = output

        # 6. Recover Phase A state exclusively from the evidence snapshot.
        phase_a_meta = dict(evidence["phase_a_metadata"])
        phase_a_gates = list(
            phase_a_meta.get("gates_evaluated", []),
        )
        all_custom_metadata = dict(
            phase_a_meta.get("all_custom_metadata", {}),
        )

        with enforcement_span(
            "aigc.enforce_post_call",
            attributes={
                "aigc.policy_file": pre_call_result.policy_file,
                "aigc.role": pre_call_result.role,
                "aigc.enforcement_mode": "split",
            },
        ) as span:
            return _run_phase_b(
                original_policy,
                original_policy,
                full_invocation,
                phase_a_gates=phase_a_gates,
                phase_a_metadata=phase_a_meta,
                phase_a_extra={
                    "preconditions_satisfied": phase_a_meta.get(
                        "preconditions_satisfied", [],
                    ),
                    "tool_constraints": phase_a_meta.get(
                        "tool_constraints", {},
                    ),
                },
                guards_evaluated_engine=list(
                    evidence.get("guards_evaluated_engine", []),
                ),
                conditions_resolved=dict(
                    evidence.get("conditions_resolved", {}),
                ),
                all_custom_metadata=all_custom_metadata,
                # Use gates captured at Phase A time, consistent with the
                # module-level path. Avoids a reachable bypass if
                # self._custom_gates is mutated between phases (Finding 1).
                grouped_gates=pre_call_result._phase_b_grouped_gates,
                sink=self._sink,
                sink_failure_mode=self._on_sink_failure,
                redaction_patterns=self._redaction_patterns,
                signer=self._signer,
                risk_config=self._risk_config,
                enforcement_mode="split",
                pre_call_timestamp=phase_a_meta.get(
                    "pre_call_timestamp",
                ),
                span=span,
            )

    async def enforce_pre_call_async(
        self, invocation: Mapping[str, Any],
    ) -> PreCallResult:
        """Async equivalent of enforce_pre_call(), instance-scoped.

        Policy file I/O runs in a thread pool via asyncio.to_thread.
        The enforcement pipeline itself is synchronous (CPU-bound).
        """
        if not isinstance(invocation, Mapping):
            _exc = InvocationValidationError(
                "Invocation must be a mapping object",
                details={"received_type": type(invocation).__name__},
            )
            _safe = {
                "policy_file": "unknown", "model_provider": "unknown",
                "model_identifier": "unknown", "role": "unknown",
                "input": {}, "output": {}, "context": {},
            }
            _artifact = _generate_pre_pipeline_fail_artifact(
                _safe, _exc,
                redaction_patterns=self._redaction_patterns,
            )
            _artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split_pre_call_only"
            )
            _exc.audit_artifact = _artifact
            try:
                emit_to_sink(
                    _artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as _sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    _sink_exc,
                )
            raise _exc

        try:
            _validate_pre_call_invocation(invocation)
            policy = await asyncio.to_thread(
                self._policy_cache.get_or_load,
                invocation["policy_file"],
                None,
                loader=self._policy_loader,
            )
            _validate_policy_strict(policy, self._strict_mode)
        except AIGCError as exc:
            safe_inv = dict(invocation)
            safe_inv.setdefault("output", {})
            artifact = _generate_pre_pipeline_fail_artifact(
                safe_inv, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "split_pre_call_only"
            )
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise

        grouped_gates = sort_gates(self._custom_gates)
        pre_call_timestamp = int(_time.time())
        # Unique per-token nonce ensures _token_hmac is unique even for
        # identical invocations in the same second (Finding 3, 2026-04-05).
        _token_nonce = os.urandom(16).hex()

        with enforcement_span(
            "aigc.enforce_pre_call",
            attributes={
                "aigc.policy_file": invocation.get("policy_file", ""),
                "aigc.role": invocation.get("role", ""),
                "aigc.enforcement_mode": "split",
            },
        ) as span:
            phase_a_gates: list[str] = []
            try:
                (
                    effective_policy,
                    guards_evaluated_engine,
                    conditions_resolved,
                    all_custom_metadata,
                    phase_a_gates,
                    phase_a_extra,
                ) = _run_phase_a(
                    policy, invocation,
                    grouped_gates=grouped_gates,
                    span=span,
                    gates_evaluated=phase_a_gates,
                )
            except AIGCError as exc:
                safe_inv = dict(invocation)
                safe_inv["output"] = {}
                audit_record = _build_phase_a_mid_pipeline_fail_artifact(
                    safe_inv, policy, exc, phase_a_gates,
                    self._redaction_patterns,
                )
                exc.audit_artifact = audit_record
                try:
                    emit_to_sink(
                        audit_record,
                        sink=self._sink,
                        failure_mode=self._on_sink_failure,
                    )
                except AuditSinkError as sink_exc:
                    logger.error(
                        "Sink emission failed on FAIL path "
                        "(artifact preserved): %s",
                        sink_exc,
                    )
                record_enforcement_result(
                    span, "FAIL",
                    policy_file=invocation.get("policy_file"),
                    role=invocation.get("role"),
                    enforcement_mode="split",
                )
                logger.error(
                    "Enforcement failed during Phase A: %s", exc,
                )
                raise

            invocation_snapshot = {
                "policy_file": invocation["policy_file"],
                "model_provider": invocation["model_provider"],
                "model_identifier": invocation["model_identifier"],
                "role": invocation["role"],
                "input": copy.deepcopy(invocation["input"]),
                "context": copy.deepcopy(invocation["context"]),
            }

            phase_a_metadata = {
                "gates_evaluated": list(phase_a_gates),
                "pre_call_timestamp": pre_call_timestamp,
                **phase_a_extra,
                "all_custom_metadata": all_custom_metadata,
            }

            record_enforcement_result(
                span, "PASS_PHASE_A",
                policy_file=invocation.get("policy_file"),
                role=invocation.get("role"),
                enforcement_mode="split",
            )

            token = PreCallResult(
                effective_policy=copy.deepcopy(effective_policy),
                resolved_guards=tuple(
                    dict(g) if isinstance(g, dict) else g
                    for g in guards_evaluated_engine
                ),
                resolved_conditions=dict(conditions_resolved),
                phase_a_metadata=phase_a_metadata,
                invocation_snapshot=invocation_snapshot,
                policy_file=invocation["policy_file"],
                model_provider=invocation["model_provider"],
                model_identifier=invocation["model_identifier"],
                role=invocation["role"],
            )
            # Use grouped_gates captured BEFORE Phase A, not a fresh sort
            # of self._custom_gates (Round 2 audit Finding 3): if a Phase A
            # gate mutates self._custom_gates, re-sorting would produce a
            # different gate set for Phase B than Phase A used.
            # Also wrap in MappingProxyType (Round 3 audit Finding 1).
            object.__setattr__(
                token, "_phase_b_grouped_gates",
                types.MappingProxyType(
                    {pt: tuple(gl) for pt, gl in grouped_gates.items()}
                ),
            )
            object.__setattr__(token, "_origin", _ENFORCEMENT_TOKEN)
            object.__setattr__(
                token, "_frozen_effective_policy",
                copy.deepcopy(token.effective_policy),
            )
            object.__setattr__(
                token, "_frozen_invocation_snapshot",
                copy.deepcopy(token.invocation_snapshot),
            )
            try:
                frozen_policy_bytes = json.dumps(
                    token.effective_policy, sort_keys=True,
                ).encode()
                frozen_evidence_bytes = json.dumps(
                    {
                        "invocation_snapshot": dict(
                            token.invocation_snapshot,
                        ),
                        "phase_a_metadata": phase_a_metadata,
                        "guards_evaluated_engine": [
                            dict(g) if isinstance(g, dict) else None
                            for g in guards_evaluated_engine
                        ],
                        "conditions_resolved": dict(conditions_resolved),
                        # Finding 1: policy in evidence so Phase B reads from signed bytes.
                        "effective_policy": dict(token.effective_policy),
                        # Finding 2: gate fingerprint so Phase B can verify _phase_b_grouped_gates.
                        "gate_fingerprint": _gate_fingerprint(grouped_gates),
                        # Finding 3: unique per-token nonce so _token_hmac is unique
                        # even for identical invocations within the same second.
                        "token_nonce": _token_nonce,
                    },
                    sort_keys=True,
                ).encode()
            except (TypeError, ValueError) as json_exc:
                freeze_err = InvocationValidationError(
                    f"Policy contains non-JSON-serializable values; "
                    f"cannot freeze token: {json_exc}",
                    details={"field": "effective_policy"},
                )
                safe_inv = dict(invocation)
                safe_inv.setdefault("output", {})
                artifact = _generate_pre_pipeline_fail_artifact(
                    safe_inv, freeze_err,
                    redaction_patterns=self._redaction_patterns,
                )
                artifact.setdefault("metadata", {})["enforcement_mode"] = (
                    "split_pre_call_only"
                )
                freeze_err.audit_artifact = artifact
                try:
                    emit_to_sink(
                        artifact,
                        sink=self._sink,
                        failure_mode=self._on_sink_failure,
                    )
                except AuditSinkError as sink_exc:
                    logger.error(
                        "Sink emission failed on policy freeze FAIL path: %s",
                        sink_exc,
                    )
                raise freeze_err from json_exc
            object.__setattr__(
                token, "_frozen_policy_bytes", frozen_policy_bytes,
            )
            object.__setattr__(
                token, "_frozen_evidence_bytes", frozen_evidence_bytes,
            )
            object.__setattr__(
                token, "_token_hmac", _token_sign(frozen_evidence_bytes),
            )
            object.__setattr__(
                token, "_frozen_phase_a_metadata",
                copy.deepcopy(phase_a_metadata),
            )
            return token

    async def enforce_post_call_async(
        self,
        pre_call_result: PreCallResult,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        """Async equivalent of enforce_post_call(), instance-scoped.

        enforce_post_call() is synchronous (CPU-bound); just delegate.
        """
        return self.enforce_post_call(pre_call_result, output)

    async def enforce_async(
        self, invocation: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Enforce governance rules (asynchronous).

        Uses instance-owned sink, failure mode, and policy cache — no global
        state is mutated (Invariant B — per-instance isolation).

        :param invocation: Invocation dict with required fields
        :return: Audit artifact dict
        :raises: AIGCError subclasses on governance violation
        """
        if not isinstance(invocation, Mapping):
            _exc = InvocationValidationError(
                "Invocation must be a mapping object",
                details={"received_type": type(invocation).__name__},
            )
            _safe = {
                "policy_file": "unknown", "model_provider": "unknown",
                "model_identifier": "unknown", "role": "unknown",
                "input": {}, "output": {}, "context": {},
            }
            _artifact = _generate_pre_pipeline_fail_artifact(
                _safe, _exc,
                redaction_patterns=self._redaction_patterns,
            )
            _artifact.setdefault("metadata", {})["enforcement_mode"] = "unified"
            _exc.audit_artifact = _artifact
            try:
                emit_to_sink(
                    _artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as _sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    _sink_exc,
                )
            raise _exc

        try:
            _validate_invocation(invocation)
            policy = await asyncio.to_thread(
                self._policy_cache.get_or_load,
                invocation["policy_file"],
                None,
                loader=self._policy_loader,
            )
            _validate_policy_strict(policy, self._strict_mode)
        except AIGCError as exc:
            artifact = _generate_pre_pipeline_fail_artifact(
                invocation, exc,
                redaction_patterns=self._redaction_patterns,
            )
            artifact.setdefault("metadata", {})["enforcement_mode"] = (
                "unified"
            )
            exc.audit_artifact = artifact
            try:
                emit_to_sink(
                    artifact,
                    sink=self._sink,
                    failure_mode=self._on_sink_failure,
                )
            except AuditSinkError as sink_exc:
                logger.error(
                    "Sink emission failed on pre-pipeline FAIL path: %s",
                    sink_exc,
                )
            raise

        return _run_pipeline(
            policy,
            invocation,
            sink=self._sink,
            sink_failure_mode=self._on_sink_failure,
            redaction_patterns=self._redaction_patterns,
            signer=self._signer,
            custom_gates=self._custom_gates,
            risk_config=self._risk_config,
        )
