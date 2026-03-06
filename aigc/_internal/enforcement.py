"""
Core enforcement logic.

Combines:
- policy loading
- validation
- error handling
- audit logging triggers
- audit sink emission
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from aigc._internal.policy_loader import load_policy
from aigc._internal.validator import (
    validate_postconditions,
    validate_preconditions,
    validate_role,
    validate_schema,
)
from aigc._internal.audit import generate_audit_artifact
from aigc._internal.guards import evaluate_guards
from aigc._internal.tools import validate_tool_constraints
from aigc._internal.sinks import emit_to_sink
from aigc._internal.errors import (
    AIGCError,
    ConditionResolutionError,
    FeatureNotImplementedError,
    GovernanceViolationError,
    GuardEvaluationError,
    InvocationValidationError,
    PolicyLoadError,
    PolicyValidationError,
    PreconditionError,
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


def _map_exception_to_failure_gate(exc: Exception) -> str:
    """Map exception type to failure gate identifier.

    Check subclasses before parent classes to ensure correct mapping.
    """
    if isinstance(exc, FeatureNotImplementedError):
        return "feature_not_implemented"
    if isinstance(exc, InvocationValidationError):
        return "invocation_validation"
    if isinstance(exc, (PolicyLoadError, PolicyValidationError)):
        return "invocation_validation"
    if isinstance(exc, GuardEvaluationError):
        return "guard_evaluation"
    if isinstance(exc, ConditionResolutionError):
        return "condition_resolution"
    if isinstance(exc, ToolConstraintViolationError):
        return "tool_validation"
    if isinstance(exc, PreconditionError):
        return "precondition_validation"
    if isinstance(exc, SchemaValidationError):
        return "schema_validation"
    if isinstance(exc, GovernanceViolationError):
        if "role" in str(exc).lower():
            return "role_validation"
        return "postcondition_validation"
    return "unknown"


def _run_pipeline(policy: dict[str, Any], invocation: Mapping[str, Any]) -> dict[str, Any]:
    """
    Run the enforcement pipeline against a pre-loaded policy.

    Shared by enforce_invocation (sync) and enforce_invocation_async (async).
    Generates and emits an audit artifact on both PASS and FAIL.

    :param policy: Pre-loaded and validated policy dict
    :param invocation: Validated invocation dict
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

    gates_evaluated: list[str] = []

    try:
        effective_policy = policy
        guards_evaluated = []
        conditions_resolved = {}
        if policy.get("guards") or policy.get("conditions"):
            logger.debug(
                "Evaluating guards and conditions for policy %s",
                invocation.get("policy_file"),
            )
            effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
                policy, invocation["context"], invocation
            )
        _record_gate(gates_evaluated, GATE_GUARDS)
        logger.debug("Guards evaluated: %d results", len(guards_evaluated))

        validate_role(invocation["role"], effective_policy)
        _record_gate(gates_evaluated, GATE_ROLE)
        logger.debug("Role validated: %s", invocation["role"])

        preconditions_satisfied = validate_preconditions(
            invocation["context"], effective_policy
        )
        _record_gate(gates_evaluated, GATE_PRECONDS)
        logger.debug("Preconditions satisfied: %s", preconditions_satisfied)

        tool_validation_result = validate_tool_constraints(
            invocation, effective_policy
        )
        _record_gate(gates_evaluated, GATE_TOOLS)
        logger.debug("Tool constraints validated")

        schema_validation = "skipped"
        schema_valid = False
        if "output_schema" in effective_policy:
            validate_schema(invocation["output"], effective_policy["output_schema"])
            schema_validation = "passed"
            schema_valid = True
            logger.debug("Output schema validation passed")
        _record_gate(gates_evaluated, GATE_SCHEMA)

        postconditions_satisfied = validate_postconditions(
            effective_policy,
            schema_valid=schema_valid,
        )
        _record_gate(gates_evaluated, GATE_POSTCONDS)
        logger.debug("Postconditions satisfied: %s", postconditions_satisfied)

        audit_record = generate_audit_artifact(
            invocation,
            policy,
            enforcement_result="PASS",
            metadata={
                "preconditions_satisfied": preconditions_satisfied,
                "postconditions_satisfied": postconditions_satisfied,
                "schema_validation": schema_validation,
                "guards_evaluated": guards_evaluated,
                "conditions_resolved": conditions_resolved,
                "tool_constraints": tool_validation_result,
                "gates_evaluated": list(gates_evaluated),
            },
        )

        emit_to_sink(audit_record)
        logger.info(
            "Enforcement complete: PASS [policy=%s, role=%s]",
            invocation.get("policy_file"),
            invocation.get("role"),
        )
        return audit_record

    except AIGCError as exc:
        failure_gate = _map_exception_to_failure_gate(exc)
        failure_reason = str(exc)

        failures = None
        if hasattr(exc, "details") and exc.details:
            failures = [
                {
                    "code": exc.__class__.__name__,
                    "message": str(exc),
                    "field": exc.details.get("field") if isinstance(exc.details, dict) else None,
                }
            ]

        audit_record = generate_audit_artifact(
            invocation,
            policy,
            enforcement_result="FAIL",
            failures=failures,
            failure_gate=failure_gate,
            failure_reason=failure_reason,
            metadata={
                "gates_evaluated": list(gates_evaluated),
            },
        )

        exc.audit_artifact = audit_record
        emit_to_sink(audit_record)
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

    _validate_invocation(invocation)
    policy = load_policy(invocation["policy_file"])
    return _run_pipeline(policy, invocation)


async def enforce_invocation_async(invocation: Mapping[str, Any]) -> dict[str, Any]:
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

    _validate_invocation(invocation)
    policy = await asyncio.to_thread(load_policy, invocation["policy_file"])
    return _run_pipeline(policy, invocation)
