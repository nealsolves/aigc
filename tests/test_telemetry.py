"""Tests for OpenTelemetry integration (M2 feature)."""
from unittest.mock import MagicMock, patch
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


# --- Tests for instrumented path (mock tracer) ---

def test_record_gate_event_with_mock_span():
    """record_gate_event sets attributes on a real span object."""
    span = MagicMock()
    record_gate_event(span, "role_validation", status="completed")
    span.set_attribute.assert_called_with(
        "aigc.gate.role_validation.status", "completed"
    )


def test_record_gate_event_with_details():
    """record_gate_event sets detail attributes filtered by type."""
    span = MagicMock()
    record_gate_event(
        span, "guard_eval",
        status="completed",
        details={
            "score": 0.85,
            "passed": True,
            "label": "ok",
            "count": 3,
        },
    )
    span.set_attribute.assert_any_call("aigc.gate.guard_eval.status", "completed")
    span.set_attribute.assert_any_call("aigc.gate.guard_eval.score", 0.85)
    span.set_attribute.assert_any_call("aigc.gate.guard_eval.passed", True)
    span.set_attribute.assert_any_call("aigc.gate.guard_eval.label", "ok")
    span.set_attribute.assert_any_call("aigc.gate.guard_eval.count", 3)


def test_record_gate_event_filters_non_primitive_details():
    """Non-primitive detail values are silently skipped."""
    span = MagicMock()
    record_gate_event(
        span, "test_gate",
        status="completed",
        details={
            "name": "valid",
            "nested": {"should": "skip"},
            "items": [1, 2, 3],
            "obj": object(),
        },
    )
    # Only status and "name" should be set (the primitives)
    calls = {call.args[0] for call in span.set_attribute.call_args_list}
    assert "aigc.gate.test_gate.status" in calls
    assert "aigc.gate.test_gate.name" in calls
    assert "aigc.gate.test_gate.nested" not in calls
    assert "aigc.gate.test_gate.items" not in calls
    assert "aigc.gate.test_gate.obj" not in calls


def test_record_gate_event_no_details():
    """record_gate_event with no details only sets status."""
    span = MagicMock()
    record_gate_event(span, "precondition", status="failed")
    assert span.set_attribute.call_count == 1
    span.set_attribute.assert_called_once_with(
        "aigc.gate.precondition.status", "failed"
    )


def test_record_gate_event_exception_resilience():
    """Exceptions in span.set_attribute are caught — governance unaffected."""
    span = MagicMock()
    span.set_attribute.side_effect = RuntimeError("OTel broken")
    # Must not raise
    record_gate_event(span, "role_validation", status="completed")


def test_record_enforcement_result_with_mock_span():
    """record_enforcement_result sets all provided attributes."""
    span = MagicMock()
    record_enforcement_result(
        span, "PASS",
        policy_file="policy.yaml",
        role="planner",
        risk_score=0.42,
    )
    span.set_attribute.assert_any_call("aigc.enforcement.result", "PASS")
    span.set_attribute.assert_any_call("aigc.enforcement.policy_file", "policy.yaml")
    span.set_attribute.assert_any_call("aigc.enforcement.role", "planner")
    span.set_attribute.assert_any_call("aigc.enforcement.risk_score", 0.42)


def test_record_enforcement_result_minimal():
    """record_enforcement_result with only result sets one attribute."""
    span = MagicMock()
    record_enforcement_result(span, "FAIL")
    assert span.set_attribute.call_count == 1
    span.set_attribute.assert_called_once_with("aigc.enforcement.result", "FAIL")


def test_record_enforcement_result_exception_resilience():
    """Exceptions in span.set_attribute are caught — governance unaffected."""
    span = MagicMock()
    span.set_attribute.side_effect = RuntimeError("OTel broken")
    # Must not raise
    record_enforcement_result(
        span, "PASS",
        policy_file="test.yaml",
        role="planner",
        risk_score=0.5,
    )


def test_enforcement_span_with_mock_tracer():
    """enforcement_span creates a real span when tracer is available."""
    import aigc._internal.telemetry as tel

    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
        return_value=mock_span
    )
    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
        return_value=False
    )

    original_available = tel._otel_available
    original_tracer = tel._tracer
    try:
        tel._otel_available = True
        tel._tracer = mock_tracer

        with enforcement_span("test.op", attributes={"key": "val"}) as span:
            assert span is mock_span

        mock_tracer.start_as_current_span.assert_called_once_with(
            "test.op", attributes={"key": "val"}
        )
    finally:
        tel._otel_available = original_available
        tel._tracer = original_tracer


def test_enforcement_span_defaults_attributes_to_empty_dict():
    """enforcement_span passes empty dict when attributes is None."""
    import aigc._internal.telemetry as tel

    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
        return_value=mock_span
    )
    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
        return_value=False
    )

    original_available = tel._otel_available
    original_tracer = tel._tracer
    try:
        tel._otel_available = True
        tel._tracer = mock_tracer

        with enforcement_span("test.op") as span:
            pass

        mock_tracer.start_as_current_span.assert_called_once_with(
            "test.op", attributes={}
        )
    finally:
        tel._otel_available = original_available
        tel._tracer = original_tracer
