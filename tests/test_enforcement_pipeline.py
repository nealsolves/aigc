import pytest

from aigc._internal.enforcement import enforce_invocation, _map_exception_to_failure_gate
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


def _base_invocation():
    return {
        "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
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
        "tests/golden_replays/policy_postcondition_without_schema.yaml"
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
        "tests/golden_replays/policy_postcondition_without_schema.yaml"
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


# --- _map_exception_to_failure_gate unit tests ---
# These cover the individual branches of the gate-mapping function directly,
# since several exception types (FeatureNotImplementedError, InvocationValidationError,
# PolicyLoadError) are raised before _run_pipeline and cannot reach it through the
# normal enforcement flow.

def test_map_feature_not_implemented():
    exc = FeatureNotImplementedError("custom_validator")
    assert _map_exception_to_failure_gate(exc) == "feature_not_implemented"


def test_map_invocation_validation_error():
    exc = InvocationValidationError("bad field", details={"field": "role"})
    assert _map_exception_to_failure_gate(exc) == "invocation_validation"


def test_map_policy_load_error():
    exc = PolicyLoadError("file missing", details={})
    assert _map_exception_to_failure_gate(exc) == "invocation_validation"


def test_map_policy_validation_error():
    exc = PolicyValidationError("schema mismatch", details={})
    assert _map_exception_to_failure_gate(exc) == "invocation_validation"


def test_map_guard_evaluation_error():
    exc = GuardEvaluationError("bad guard", details={})
    assert _map_exception_to_failure_gate(exc) == "guard_evaluation"


def test_map_condition_resolution_error():
    exc = ConditionResolutionError("missing condition", details={})
    assert _map_exception_to_failure_gate(exc) == "condition_resolution"


def test_map_tool_constraint_violation():
    exc = ToolConstraintViolationError("too many calls", details={})
    assert _map_exception_to_failure_gate(exc) == "tool_validation"


def test_map_precondition_error():
    exc = PreconditionError("missing key", details={})
    assert _map_exception_to_failure_gate(exc) == "precondition_validation"


def test_map_schema_validation_error():
    exc = SchemaValidationError("bad output", details={})
    assert _map_exception_to_failure_gate(exc) == "schema_validation"


def test_map_governance_violation_role():
    exc = GovernanceViolationError("Unauthorized role 'attacker'", code="ROLE_NOT_ALLOWED")
    assert _map_exception_to_failure_gate(exc) == "role_validation"


def test_map_governance_violation_postcondition():
    exc = GovernanceViolationError("Postcondition failed", code="POSTCONDITION_FAILED")
    assert _map_exception_to_failure_gate(exc) == "postcondition_validation"


def test_map_unknown_aigc_error():
    """An AIGCError subclass that does not match any known gate returns 'unknown'."""

    class _UnknownAIGCError(AIGCError):
        def __init__(self):
            super().__init__("unknown failure", code="UNKNOWN")

    exc = _UnknownAIGCError()
    assert _map_exception_to_failure_gate(exc) == "unknown"


# --- AIGC instance tests ---

from aigc._internal.enforcement import AIGC


def test_aigc_instance_enforce_passes():
    """AIGC instance enforce() produces same result as module-level function."""
    aigc = AIGC()
    invocation = _base_invocation()
    audit = aigc.enforce(invocation)
    assert audit["enforcement_result"] == "PASS"
    assert audit["policy_file"] == invocation["policy_file"]


def test_aigc_instance_enforce_raises_on_violation():
    """AIGC instance enforce() raises on governance violation."""
    aigc = AIGC()
    invocation = _base_invocation()
    invocation["role"] = "attacker"
    with pytest.raises(GovernanceViolationError) as exc_info:
        aigc.enforce(invocation)
    assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"


def test_aigc_instance_invalid_on_sink_failure():
    """AIGC rejects invalid on_sink_failure value."""
    with pytest.raises(ValueError, match="on_sink_failure"):
        AIGC(on_sink_failure="invalid")


def test_aigc_instance_config_properties():
    """AIGC instance exposes config as read-only properties."""
    aigc = AIGC(strict_mode=True, on_sink_failure="raise")
    assert aigc.strict_mode is True
    assert aigc.on_sink_failure == "raise"
    assert aigc.sink is None


async def test_aigc_instance_enforce_async_passes():
    """AIGC instance enforce_async() works correctly."""
    aigc = AIGC()
    invocation = _base_invocation()
    audit = await aigc.enforce_async(invocation)
    assert audit["enforcement_result"] == "PASS"


def test_aigc_instance_thread_safety():
    """AIGC instance enforce() is safe from multiple threads."""
    import concurrent.futures

    aigc = AIGC()

    def enforce_once():
        invocation = _base_invocation()
        return aigc.enforce(invocation)

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(enforce_once) for _ in range(50)]
        results = [f.result() for f in futures]

    assert all(r["enforcement_result"] == "PASS" for r in results)
    assert len(results) == 50
