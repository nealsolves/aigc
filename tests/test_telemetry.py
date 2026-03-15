"""Tests for OpenTelemetry integration (M2 feature)."""
from aigc._internal.telemetry import (
    is_otel_available,
    enforcement_span,
    record_gate_event,
    record_enforcement_result,
)


def test_otel_availability_check():
    """is_otel_available returns a boolean."""
    result = is_otel_available()
    assert isinstance(result, bool)


def test_enforcement_span_noop_without_otel():
    """When OTel is not installed, span context yields None."""
    with enforcement_span("test.span") as span:
        # If OTel is not installed, span should be None
        # If OTel IS installed, span should be a valid span
        # Either way, this should not crash
        record_gate_event(span, "test_gate", status="completed")


def test_record_gate_event_noop_on_none():
    """record_gate_event is a no-op when span is None."""
    record_gate_event(None, "test_gate")  # Should not raise


def test_record_enforcement_result_noop_on_none():
    """record_enforcement_result is a no-op when span is None."""
    record_enforcement_result(
        None, "PASS",
        policy_file="test.yaml",
        role="planner",
        risk_score=0.5,
    )  # Should not raise


def test_governance_unaffected_by_telemetry():
    """Enforcement works identically whether OTel is available or not."""
    from aigc._internal.enforcement import enforce_invocation

    invocation = {
        "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {"prompt": "test"},
        "output": {"result": "ok", "confidence": 0.9},
        "context": {"role_declared": True, "schema_exists": True},
    }

    audit = enforce_invocation(invocation)
    assert audit["enforcement_result"] == "PASS"


def test_span_with_attributes():
    """Span creation with attributes does not crash."""
    with enforcement_span(
        "test.span",
        attributes={"key": "value", "number": 42},
    ) as span:
        record_gate_event(
            span, "test_gate",
            status="completed",
            details={"score": 0.5, "passed": True},
        )
