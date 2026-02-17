import pytest

from src.enforcement import enforce_invocation
from src.errors import (
    FeatureNotImplementedError,
    GovernanceViolationError,
    PreconditionError,
    SchemaValidationError,
)


def _base_invocation():
    return {
        "policy_file": "tests/golden_traces/golden_policy_v1.yaml",
        "model_provider": "openai",
        "model_identifier": "gpt-test-model",
        "role": "planner",
        "input": {"task": "describe system"},
        "output": {"result": "description", "confidence": 0.99},
        "context": {"role_declared": True, "schema_exists": True},
    }


def test_unauthorized_role_fails_closed():
    invocation = _base_invocation()
    invocation["role"] = "attacker"
    with pytest.raises(GovernanceViolationError) as exc_info:
        enforce_invocation(invocation)
    assert exc_info.value.code == "ROLE_NOT_ALLOWED"


def test_missing_precondition_fails_closed():
    invocation = _base_invocation()
    invocation["context"] = {"role_declared": True}
    with pytest.raises(PreconditionError) as exc_info:
        enforce_invocation(invocation)
    assert exc_info.value.code == "PRECONDITION_FAILED"


def test_invalid_output_schema_fails_closed():
    invocation = _base_invocation()
    invocation["output"] = {"result": "description"}
    with pytest.raises(SchemaValidationError) as exc_info:
        enforce_invocation(invocation)
    assert exc_info.value.code == "OUTPUT_SCHEMA_VALIDATION_ERROR"


def test_postcondition_requires_schema_validation():
    invocation = _base_invocation()
    invocation["policy_file"] = (
        "tests/golden_traces/policy_postcondition_without_schema.yaml"
    )
    with pytest.raises(GovernanceViolationError) as exc_info:
        enforce_invocation(invocation)
    assert exc_info.value.code == "POSTCONDITION_FAILED"


# Phase 2 features (guards, tools, retry_policy) are now all implemented
# No unimplemented features remain in Phase 2


# Phase 1.8: Failure audit artifact emission tests


def test_role_failure_emits_audit_artifact():
    """Verify that role validation failures emit FAIL audit artifacts."""
    invocation = _base_invocation()
    invocation["role"] = "attacker"

    with pytest.raises(GovernanceViolationError) as exc_info:
        enforce_invocation(invocation)

    # Verify exception has audit artifact attached
    assert hasattr(exc_info.value, "audit_artifact")
    audit = exc_info.value.audit_artifact

    # Verify FAIL audit structure
    assert audit["enforcement_result"] == "FAIL"
    assert audit["failure_gate"] == "role_validation"
    assert audit["failure_reason"] is not None
    assert "role" in audit["failure_reason"].lower()

    # Verify stable audit fields still present
    assert audit["model_provider"] == "openai"
    assert audit["model_identifier"] == "gpt-test-model"
    assert audit["role"] == "attacker"
    assert "input_checksum" in audit
    assert "output_checksum" in audit
    assert "timestamp" in audit


def test_precondition_failure_emits_audit_artifact():
    """Verify that precondition failures emit FAIL audit artifacts."""
    invocation = _base_invocation()
    invocation["context"] = {"role_declared": True}  # missing schema_exists

    with pytest.raises(PreconditionError) as exc_info:
        enforce_invocation(invocation)

    # Verify exception has audit artifact attached
    assert hasattr(exc_info.value, "audit_artifact")
    audit = exc_info.value.audit_artifact

    # Verify FAIL audit structure
    assert audit["enforcement_result"] == "FAIL"
    assert audit["failure_gate"] == "precondition_validation"
    assert audit["failure_reason"] is not None

    # Verify stable fields
    assert audit["model_provider"] == "openai"
    assert "input_checksum" in audit


def test_schema_failure_emits_audit_artifact():
    """Verify that schema validation failures emit FAIL audit artifacts."""
    invocation = _base_invocation()
    invocation["output"] = {"result": "description"}  # missing confidence field

    with pytest.raises(SchemaValidationError) as exc_info:
        enforce_invocation(invocation)

    # Verify exception has audit artifact attached
    assert hasattr(exc_info.value, "audit_artifact")
    audit = exc_info.value.audit_artifact

    # Verify FAIL audit structure
    assert audit["enforcement_result"] == "FAIL"
    assert audit["failure_gate"] == "schema_validation"
    assert audit["failure_reason"] is not None

    # Verify stable fields
    assert audit["model_provider"] == "openai"
    assert "input_checksum" in audit


def test_postcondition_failure_emits_audit_artifact():
    """Verify that postcondition failures emit FAIL audit artifacts."""
    invocation = _base_invocation()
    invocation["policy_file"] = (
        "tests/golden_traces/policy_postcondition_without_schema.yaml"
    )

    with pytest.raises(GovernanceViolationError) as exc_info:
        enforce_invocation(invocation)

    # Verify exception has audit artifact attached
    assert hasattr(exc_info.value, "audit_artifact")
    audit = exc_info.value.audit_artifact

    # Verify FAIL audit structure
    assert audit["enforcement_result"] == "FAIL"
    assert audit["failure_gate"] == "postcondition_validation"
    assert audit["failure_reason"] is not None

    # Verify stable fields
    assert audit["model_provider"] == "openai"


def test_success_has_null_failure_fields():
    """Verify that successful enforcement has null failure_gate and failure_reason."""
    invocation = _base_invocation()
    audit = enforce_invocation(invocation)

    # Verify PASS audit structure
    assert audit["enforcement_result"] == "PASS"
    assert audit["failure_gate"] is None
    assert audit["failure_reason"] is None
    assert audit["failures"] == []
