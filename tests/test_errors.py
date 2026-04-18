"""Unit tests for the custom error taxonomy."""

import pytest

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
    WorkflowApprovalRequiredError,
    WorkflowSessionTokenInvalidError,
    WorkflowSourceRequiredError,
    WorkflowToolBudgetExceededError,
    WorkflowUnsupportedBindingError,
)


def test_feature_not_implemented_error_instantiation():
    """FeatureNotImplementedError stores feature name and uses correct code (errors.py:92)."""
    exc = FeatureNotImplementedError("custom_validator")
    assert exc.code == "FEATURE_NOT_IMPLEMENTED"
    assert "custom_validator" in str(exc)
    assert exc.details["feature"] == "custom_validator"


def test_feature_not_implemented_is_governance_violation():
    assert isinstance(FeatureNotImplementedError("x"), GovernanceViolationError)
    assert isinstance(FeatureNotImplementedError("x"), AIGCError)


def test_governance_violation_default_code():
    exc = GovernanceViolationError("something went wrong")
    assert exc.code == "GOVERNANCE_VIOLATION"
    assert exc.details == {}


def test_governance_violation_custom_code():
    exc = GovernanceViolationError("role denied", code="ROLE_NOT_ALLOWED", details={"role": "attacker"})
    assert exc.code == "ROLE_NOT_ALLOWED"
    assert exc.details["role"] == "attacker"


def test_invocation_validation_error():
    exc = InvocationValidationError("bad field", details={"field": "role"})
    assert exc.code == "INVOCATION_VALIDATION_ERROR"
    assert exc.details["field"] == "role"
    assert isinstance(exc, GovernanceViolationError)


def test_policy_load_error():
    exc = PolicyLoadError("not found")
    assert exc.code == "POLICY_LOAD_ERROR"
    assert isinstance(exc, GovernanceViolationError)


def test_policy_validation_error():
    exc = PolicyValidationError("schema mismatch")
    assert exc.code == "POLICY_SCHEMA_VALIDATION_ERROR"
    assert isinstance(exc, GovernanceViolationError)


def test_schema_validation_error():
    exc = SchemaValidationError("output invalid", details={"path": "$.result"})
    assert exc.code == "OUTPUT_SCHEMA_VALIDATION_ERROR"
    assert exc.details["path"] == "$.result"
    assert isinstance(exc, AIGCError)
    # SchemaValidationError is NOT a GovernanceViolationError (retryable)
    assert not isinstance(exc, GovernanceViolationError)


def test_precondition_error():
    exc = PreconditionError("missing key", details={"precondition": "role_declared"})
    assert exc.code == "PRECONDITION_FAILED"
    assert isinstance(exc, AIGCError)
    assert not isinstance(exc, GovernanceViolationError)


def test_condition_resolution_error():
    exc = ConditionResolutionError("missing condition")
    assert exc.code == "CONDITION_RESOLUTION_ERROR"
    assert isinstance(exc, AIGCError)


def test_guard_evaluation_error():
    exc = GuardEvaluationError("bad expression")
    assert exc.code == "GUARD_EVALUATION_ERROR"
    assert isinstance(exc, AIGCError)


def test_tool_constraint_violation_error():
    exc = ToolConstraintViolationError("max calls exceeded", details={"tool": "search"})
    assert exc.code == "TOOL_CONSTRAINT_VIOLATION"
    assert isinstance(exc, GovernanceViolationError)


def test_audit_artifact_attached_after_failure():
    """audit_artifact attribute is None by default and can be set."""
    exc = PreconditionError("test")
    assert exc.audit_artifact is None
    exc.audit_artifact = {"enforcement_result": "FAIL"}
    assert exc.audit_artifact["enforcement_result"] == "FAIL"


# ---------------------------------------------------------------------------
# PR-06 frozen workflow reason-code error classes
# ---------------------------------------------------------------------------

def test_workflow_approval_required_error():
    exc = WorkflowApprovalRequiredError("approval needed")
    assert exc.code == "WORKFLOW_APPROVAL_REQUIRED"
    assert "approval needed" in str(exc)
    assert isinstance(exc, GovernanceViolationError)
    assert isinstance(exc, AIGCError)


def test_workflow_source_required_error():
    exc = WorkflowSourceRequiredError("source IDs missing", details={"gate": "ProvenanceGate"})
    assert exc.code == "WORKFLOW_SOURCE_REQUIRED"
    assert exc.details["gate"] == "ProvenanceGate"
    assert isinstance(exc, GovernanceViolationError)


def test_workflow_tool_budget_exceeded_error():
    exc = WorkflowToolBudgetExceededError("search exceeded max_calls")
    assert exc.code == "WORKFLOW_TOOL_BUDGET_EXCEEDED"
    assert isinstance(exc, GovernanceViolationError)


def test_workflow_unsupported_binding_error():
    exc = WorkflowUnsupportedBindingError("gRPC not supported")
    assert exc.code == "WORKFLOW_UNSUPPORTED_BINDING"
    assert isinstance(exc, GovernanceViolationError)


def test_workflow_session_token_invalid_error():
    exc = WorkflowSessionTokenInvalidError("token already consumed")
    assert exc.code == "WORKFLOW_SESSION_TOKEN_INVALID"
    # WorkflowSessionTokenInvalidError extends AIGCError (not GovernanceViolationError)
    assert isinstance(exc, AIGCError)
    assert not isinstance(exc, GovernanceViolationError)


def test_workflow_pr06_errors_have_audit_artifact_attribute():
    """All PR-06 error classes inherit audit_artifact from AIGCError."""
    for cls in (
        WorkflowApprovalRequiredError,
        WorkflowSourceRequiredError,
        WorkflowToolBudgetExceededError,
        WorkflowUnsupportedBindingError,
        WorkflowSessionTokenInvalidError,
    ):
        exc = cls("test")
        assert exc.audit_artifact is None
