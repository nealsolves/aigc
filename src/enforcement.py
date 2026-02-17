"""
Core enforcement logic.

Combines:
- policy loading
- validation
- error handling
- audit logging triggers
"""

from __future__ import annotations

from typing import Any, Mapping

from src.policy_loader import load_policy
from src.validator import (
    validate_postconditions,
    validate_preconditions,
    validate_role,
    validate_schema,
)
from src.audit import generate_audit_artifact
from src.guards import evaluate_guards
from src.tools import validate_tool_constraints
from src.errors import (
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
    # Check most specific exceptions first
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
    # Generic GovernanceViolationError (base class) - check last
    if isinstance(exc, GovernanceViolationError):
        # Could be role or postcondition - check message
        if "role" in str(exc).lower():
            return "role_validation"
        return "postcondition_validation"
    return "unknown"


def enforce_invocation(invocation: Mapping[str, Any]) -> dict[str, Any]:
    """
    Enforce all governance rules for a model invocation.

    :param invocation: Dict with:
      - "policy_file": path to policy
      - "input": model input
      - "output": model output (to be validated)
      - "context": additional context
    :return: audit artifact (PASS or FAIL)
    :raises: AIGCError subclasses on governance violation (after audit emission)
    """
    if not isinstance(invocation, Mapping):
        raise InvocationValidationError(
            "Invocation must be a mapping object",
            details={"received_type": type(invocation).__name__},
        )

    _validate_invocation(invocation)

    # Load policy (needed for audit artifact generation)
    policy = load_policy(invocation["policy_file"])

    try:
        # Phase 2 features - guards/tools/retry all implemented
        # Retry is opt-in via with_retry() wrapper in src/retry.py

        # Evaluate guards to produce effective policy (Phase 2.1)
        effective_policy = policy
        guards_evaluated = []
        conditions_resolved = {}
        if policy.get("guards") or policy.get("conditions"):
            effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
                policy, invocation["context"], invocation
            )

        # Validate role allowlist
        validate_role(invocation["role"], effective_policy)

        # Validate preconditions
        preconditions_satisfied = validate_preconditions(
            invocation["context"], effective_policy
        )

        # Validate output schema (if provided in policy)
        schema_validation = "skipped"
        schema_valid = False
        if "output_schema" in effective_policy:
            validate_schema(invocation["output"], effective_policy["output_schema"])
            schema_validation = "passed"
            schema_valid = True

        postconditions_satisfied = validate_postconditions(
            effective_policy,
            schema_valid=schema_valid,
        )

        # Validate tool constraints (Phase 2.3)
        tool_validation_result = validate_tool_constraints(
            invocation, effective_policy
        )

        # Generate PASS audit artifact
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
            },
        )

        return audit_record

    except AIGCError as exc:
        # Generate FAIL audit artifact before re-raising
        failure_gate = _map_exception_to_failure_gate(exc)
        failure_reason = str(exc)

        # Extract structured failures from exception if available
        failures = None
        if hasattr(exc, "details") and exc.details:
            # Convert exception details to failure format
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
            metadata={},
        )

        # Store audit record on exception for caller to retrieve
        exc.audit_artifact = audit_record

        # Re-raise original exception (fail-closed)
        raise
