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


REQUIRED_INVOCATION_KEYS = (
    "policy_file",
    "model_provider",
    "model_identifier",
    "role",
    "input",
    "output",
    "context",
)


def _validate_invocation(invocation: Mapping[str, Any]) -> None:
    missing = [key for key in REQUIRED_INVOCATION_KEYS if key not in invocation]
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

    object_keys = ("input", "output", "context")
    for key in object_keys:
        if not isinstance(invocation[key], dict):
            raise InvocationValidationError(
                f"Invocation field '{key}' must be an object",
                details={"field": key},
            )

    for key in object_keys:
        try:
            json.dumps(invocation[key])
        except (TypeError, ValueError) as e:
            raise InvocationValidationError(
                f"Invocation field '{key}' is not JSON-serializable: {e}",
                details={"field": key},
            ) from e


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
    # ── PIPELINE_CONTRACT ────────────────────────────────────────
    # Do not reorder authorization gates after output gates.
    # Authorization: guard_evaluation → role_validation →
    #                precondition_validation → tool_constraint_validation
    # Output:        schema_validation → postcondition_validation
    # Enforced by:   tests/test_pre_action_boundary.py
    # ─────────────────────────────────────────────────────────────

    # Build sink kwargs for emit_to_sink calls in this pipeline run.
    # When sink is explicitly provided, pass it through; otherwise use sentinel
    # so emit_to_sink falls back to the global default.
    _sink_kw: dict[str, Any] = {}
    if sink is not None:
        _sink_kw["sink"] = sink
    if sink_failure_mode is not None:
        _sink_kw["failure_mode"] = sink_failure_mode

    gates_evaluated: list[str] = []
    grouped_gates = sort_gates(custom_gates or [])

    with enforcement_span(
        "aigc.enforce_invocation",
        attributes={
            "aigc.policy_file": invocation.get("policy_file", ""),
            "aigc.role": invocation.get("role", ""),
        },
    ) as span:
        try:
            # Accumulated custom gate metadata (merged deterministically
            # into the audit artifact under "custom_gate_metadata").
            all_custom_metadata: dict[str, Any] = {}

            def _run_custom_gates_at(
                insertion_point: str,
                policy_view: dict[str, Any],
            ) -> None:
                """Run custom gates at the given insertion point.

                Raises CustomGateViolationError on failure so the failure
                mapper can classify it correctly.
                """
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

            # ── Pre-authorization custom gates ──────────────
            _run_custom_gates_at(INSERTION_PRE_AUTHORIZATION, policy)

            effective_policy = policy
            guards_evaluated = []
            conditions_resolved = {}
            if policy.get("guards") or policy.get("conditions"):
                logger.debug(
                    "Evaluating guards and conditions for policy %s",
                    invocation.get("policy_file"),
                )
                effective_policy, guards_evaluated, conditions_resolved = (
                    evaluate_guards(policy, invocation["context"], invocation)
                )
            _record_gate(gates_evaluated, GATE_GUARDS)
            record_gate_event(span, GATE_GUARDS)
            logger.debug("Guards evaluated: %d results", len(guards_evaluated))

            validate_role(invocation["role"], effective_policy)
            _record_gate(gates_evaluated, GATE_ROLE)
            record_gate_event(span, GATE_ROLE)
            logger.debug("Role validated: %s", invocation["role"])

            preconditions_satisfied = validate_preconditions(
                invocation["context"], effective_policy
            )
            _record_gate(gates_evaluated, GATE_PRECONDS)
            record_gate_event(span, GATE_PRECONDS)
            logger.debug("Preconditions satisfied: %s", preconditions_satisfied)

            tool_validation_result = validate_tool_constraints(
                invocation, effective_policy
            )
            _record_gate(gates_evaluated, GATE_TOOLS)
            record_gate_event(span, GATE_TOOLS)
            logger.debug("Tool constraints validated")

            # ── Post-authorization custom gates ─────────────
            _run_custom_gates_at(
                INSERTION_POST_AUTHORIZATION, effective_policy,
            )

            # ── Pre-output custom gates ─────────────────────
            _run_custom_gates_at(INSERTION_PRE_OUTPUT, effective_policy)

            schema_validation = "skipped"
            schema_valid = False
            if "output_schema" in effective_policy:
                validate_schema(
                    invocation["output"], effective_policy["output_schema"]
                )
                schema_validation = "passed"
                schema_valid = True
                logger.debug("Output schema validation passed")
            _record_gate(gates_evaluated, GATE_SCHEMA)
            record_gate_event(span, GATE_SCHEMA)

            postconditions_satisfied = validate_postconditions(
                effective_policy,
                schema_valid=schema_valid,
            )
            _record_gate(gates_evaluated, GATE_POSTCONDS)
            record_gate_event(span, GATE_POSTCONDS)
            logger.debug(
                "Postconditions satisfied: %s", postconditions_satisfied
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
                _record_gate(gates_evaluated, GATE_RISK)
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
                            "(warn_only mode — not blocking)",
                            risk_result.score,
                            risk_result.threshold,
                        )

            metadata = {
                "preconditions_satisfied": preconditions_satisfied,
                "postconditions_satisfied": postconditions_satisfied,
                "schema_validation": schema_validation,
                "guards_evaluated": guards_evaluated,
                "conditions_resolved": conditions_resolved,
                "tool_constraints": tool_validation_result,
                "gates_evaluated": list(gates_evaluated),
            }

            if all_custom_metadata:
                metadata["custom_gate_metadata"] = dict(
                    sorted(all_custom_metadata.items())
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
            failure_gate = _map_exception_to_failure_gate(exc)
            raw_reason = str(exc)
            failure_reason, reason_redacted = sanitize_failure_message(
                raw_reason, redaction_patterns
            )

            redacted_fields: list[str] = list(reason_redacted)
            failures = None
            if hasattr(exc, "details") and exc.details:
                sanitized_msg, msg_redacted = sanitize_failure_message(
                    str(exc), redaction_patterns
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
                "gates_evaluated": list(gates_evaluated),
                "redacted_fields": redacted_fields,
            }
            if isinstance(exc, RiskThresholdError) and isinstance(
                getattr(exc, "details", None), dict
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
