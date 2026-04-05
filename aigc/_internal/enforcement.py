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
import json
import logging
import re
import time as _time
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
            json.dumps(invocation[key])
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
        json.dumps(invocation["output"])
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
        raise InvocationValidationError(
            "Invocation must be a mapping object",
            details={"received_type": type(invocation).__name__},
        )

    try:
        _validate_invocation(invocation)
        policy = load_policy(invocation["policy_file"])
    except AIGCError as exc:
        artifact = _generate_pre_pipeline_fail_artifact(invocation, exc)
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
        raise InvocationValidationError(
            "Invocation must be a mapping object",
            details={"received_type": type(invocation).__name__},
        )

    try:
        _validate_invocation(invocation)
        policy = await asyncio.to_thread(
            load_policy, invocation["policy_file"]
        )
    except AIGCError as exc:
        artifact = _generate_pre_pipeline_fail_artifact(invocation, exc)
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
        raise InvocationValidationError(
            "Invocation must be a mapping object",
            details={"received_type": type(invocation).__name__},
        )

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
            )
            logger.error(
                "Enforcement failed at gate '%s': %s",
                failure_gate,
                failure_reason,
            )
            raise

        # Build invocation snapshot (exactly 6 required fields, no output)
        invocation_snapshot = {
            "policy_file": invocation["policy_file"],
            "model_provider": invocation["model_provider"],
            "model_identifier": invocation["model_identifier"],
            "role": invocation["role"],
            "input": invocation["input"],
            "context": invocation["context"],
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
        )

        return PreCallResult(
            effective_policy=effective_policy,
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

    # 2. Output validation
    if not isinstance(output, dict):
        exc = InvocationValidationError(
            "enforce_post_call() output must be a dict",
            details={"field": "output"},
        )
        safe_inv = dict(pre_call_result.invocation_snapshot)
        safe_inv["output"] = {}
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

    # 3. Consumption check
    if pre_call_result._consumed:
        exc = InvocationValidationError(
            "PreCallResult has already been consumed; "
            "create a new one via enforce_pre_call()",
            details={"field": "pre_call_result"},
        )
        safe_inv = dict(pre_call_result.invocation_snapshot)
        safe_inv["output"] = {}
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

    # 4. Mark consumed (frozen dataclass requires object.__setattr__)
    object.__setattr__(pre_call_result, "_consumed", True)

    # 5. Build full invocation for Phase B
    full_invocation = dict(pre_call_result.invocation_snapshot)
    full_invocation["output"] = output

    # 6. Recover Phase A state
    phase_a_meta = dict(pre_call_result.phase_a_metadata)
    phase_a_gates = list(
        phase_a_meta.get("gates_evaluated", []),
    )
    all_custom_metadata = dict(
        phase_a_meta.get("all_custom_metadata", {}),
    )

    # Reload the original policy for artifact generation (policy_version etc.)
    # We use the effective_policy's original data; for the artifact we need
    # the raw policy. We store the effective_policy; the original policy is
    # needed only for policy_version metadata. Since the effective_policy
    # is derived from the original, we pass it as the policy arg too.
    original_policy = dict(pre_call_result.effective_policy)

    with enforcement_span(
        "aigc.enforce_post_call",
        attributes={
            "aigc.policy_file": pre_call_result.policy_file,
            "aigc.role": pre_call_result.role,
            "aigc.enforcement_mode": "split",
        },
    ) as span:
        return _run_phase_b(
            dict(pre_call_result.effective_policy),
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
                pre_call_result.resolved_guards,
            ),
            conditions_resolved=dict(
                pre_call_result.resolved_conditions,
            ),
            all_custom_metadata=all_custom_metadata,
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
        raise InvocationValidationError(
            "Invocation must be a mapping object",
            details={"received_type": type(invocation).__name__},
        )

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
            "input": invocation["input"],
            "context": invocation["context"],
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
        )

        return PreCallResult(
            effective_policy=effective_policy,
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
            json.dumps(v)
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
            raise InvocationValidationError(
                "Invocation must be a mapping object",
                details={"received_type": type(invocation).__name__},
            )

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
            raise InvocationValidationError(
                "Invocation must be a mapping object",
                details={"received_type": type(invocation).__name__},
            )

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
