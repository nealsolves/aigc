"""Tests for split-enforcement telemetry span behavior (Step 6 — v0.3.2)."""
from unittest.mock import MagicMock, patch, call
import pytest

import aigc._internal.telemetry as tel
from aigc._internal.telemetry import (
    enforcement_span,
    record_enforcement_result,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_tracer():
    """Return a (mock_tracer, mock_span) pair wired for context-manager use."""
    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
        return_value=mock_span
    )
    mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
        return_value=False
    )
    return mock_tracer, mock_span


def _golden_invocation():
    """Return a minimal passing invocation."""
    return {
        "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {"prompt": "test"},
        "output": {"result": "ok", "confidence": 0.9},
        "context": {"role_declared": True, "schema_exists": True},
    }


def _golden_pre_call_invocation():
    """Return a minimal pre-call invocation (no output)."""
    inv = _golden_invocation()
    del inv["output"]
    return inv


# ---------------------------------------------------------------------------
# Test 1: split pre-call span name
# ---------------------------------------------------------------------------

def test_split_pre_call_span_name():
    """enforce_pre_call() opens a span named 'aigc.enforce_pre_call'."""
    from aigc._internal.enforcement import enforce_pre_call, enforce_post_call

    mock_tracer, mock_span = _make_mock_tracer()

    original_available = tel._otel_available
    original_tracer = tel._tracer
    try:
        tel._otel_available = True
        tel._tracer = mock_tracer

        pre_result = enforce_pre_call(_golden_pre_call_invocation())
        # Consume the result
        enforce_post_call(pre_result, {"result": "ok", "confidence": 0.9})
    finally:
        tel._otel_available = original_available
        tel._tracer = original_tracer

    # At least one call to start_as_current_span used "aigc.enforce_pre_call"
    span_names = [
        c.args[0]
        for c in mock_tracer.start_as_current_span.call_args_list
    ]
    assert "aigc.enforce_pre_call" in span_names, (
        f"Expected 'aigc.enforce_pre_call' in span names; got {span_names}"
    )


# ---------------------------------------------------------------------------
# Test 2: split post-call span name
# ---------------------------------------------------------------------------

def test_split_post_call_span_name():
    """enforce_post_call() opens a span named 'aigc.enforce_post_call'."""
    from aigc._internal.enforcement import enforce_pre_call, enforce_post_call

    mock_tracer, mock_span = _make_mock_tracer()

    original_available = tel._otel_available
    original_tracer = tel._tracer
    try:
        tel._otel_available = True
        tel._tracer = mock_tracer

        pre_result = enforce_pre_call(_golden_pre_call_invocation())
        enforce_post_call(pre_result, {"result": "ok", "confidence": 0.9})
    finally:
        tel._otel_available = original_available
        tel._tracer = original_tracer

    span_names = [
        c.args[0]
        for c in mock_tracer.start_as_current_span.call_args_list
    ]
    assert "aigc.enforce_post_call" in span_names, (
        f"Expected 'aigc.enforce_post_call' in span names; got {span_names}"
    )


# ---------------------------------------------------------------------------
# Test 3: unified mode span name unchanged
# ---------------------------------------------------------------------------

def test_unified_span_name_unchanged():
    """enforce_invocation() still opens a span named 'aigc.enforce_invocation'."""
    from aigc._internal.enforcement import enforce_invocation

    mock_tracer, mock_span = _make_mock_tracer()

    original_available = tel._otel_available
    original_tracer = tel._tracer
    try:
        tel._otel_available = True
        tel._tracer = mock_tracer

        enforce_invocation(_golden_invocation())
    finally:
        tel._otel_available = original_available
        tel._tracer = original_tracer

    span_names = [
        c.args[0]
        for c in mock_tracer.start_as_current_span.call_args_list
    ]
    assert "aigc.enforce_invocation" in span_names, (
        f"Expected 'aigc.enforce_invocation' in span names; got {span_names}"
    )
    # Unified mode must NOT open the split span names
    assert "aigc.enforce_pre_call" not in span_names
    assert "aigc.enforce_post_call" not in span_names


# ---------------------------------------------------------------------------
# Test 4: enforcement_mode attribute set on span via record_enforcement_result
# ---------------------------------------------------------------------------

def test_enforcement_mode_attribute_set_on_span():
    """record_enforcement_result sets 'aigc.enforcement_mode' when provided."""
    span = MagicMock()
    record_enforcement_result(
        span, "PASS",
        policy_file="policy.yaml",
        role="planner",
        enforcement_mode="split",
    )
    span.set_attribute.assert_any_call("aigc.enforcement_mode", "split")


def test_enforcement_mode_attribute_unified():
    """record_enforcement_result sets 'aigc.enforcement_mode' to 'unified'."""
    span = MagicMock()
    record_enforcement_result(
        span, "PASS",
        policy_file="policy.yaml",
        role="planner",
        enforcement_mode="unified",
    )
    span.set_attribute.assert_any_call("aigc.enforcement_mode", "unified")


def test_enforcement_mode_not_set_when_none():
    """record_enforcement_result does NOT set enforcement_mode when not provided."""
    span = MagicMock()
    record_enforcement_result(span, "PASS", policy_file="policy.yaml")
    # Verify the attribute key was NOT set
    attr_keys = [c.args[0] for c in span.set_attribute.call_args_list]
    assert "aigc.enforcement_mode" not in attr_keys


# ---------------------------------------------------------------------------
# Test 5: OTel unavailable — enforcement still succeeds
# ---------------------------------------------------------------------------

def test_telemetry_unavailable_does_not_affect_enforcement():
    """When OTel is unavailable (default in CI), split enforcement still works."""
    from aigc._internal.enforcement import enforce_pre_call, enforce_post_call

    # Guarantee OTel is disabled for this test
    original_available = tel._otel_available
    original_tracer = tel._tracer
    try:
        tel._otel_available = False
        tel._tracer = None

        pre_result = enforce_pre_call(_golden_pre_call_invocation())
        audit = enforce_post_call(
            pre_result, {"result": "ok", "confidence": 0.9}
        )
    finally:
        tel._otel_available = original_available
        tel._tracer = original_tracer

    assert audit["enforcement_result"] == "PASS"
    assert audit.get("metadata", {}).get("enforcement_mode") == "split"


# ---------------------------------------------------------------------------
# Test 6: split span carries aigc.enforcement_mode span attribute
# ---------------------------------------------------------------------------

def test_split_pre_call_span_carries_enforcement_mode_attribute():
    """The span opened by enforce_pre_call() carries aigc.enforcement_mode='split'."""
    from aigc._internal.enforcement import enforce_pre_call, enforce_post_call

    mock_tracer, mock_span = _make_mock_tracer()

    original_available = tel._otel_available
    original_tracer = tel._tracer
    try:
        tel._otel_available = True
        tel._tracer = mock_tracer

        pre_result = enforce_pre_call(_golden_pre_call_invocation())
        enforce_post_call(pre_result, {"result": "ok", "confidence": 0.9})
    finally:
        tel._otel_available = original_available
        tel._tracer = original_tracer

    # Find the call that opened the pre_call span and check attributes
    pre_call_attrs = None
    for c in mock_tracer.start_as_current_span.call_args_list:
        if c.args[0] == "aigc.enforce_pre_call":
            pre_call_attrs = c.kwargs.get("attributes") or {}
            break

    assert pre_call_attrs is not None, "pre_call span was not opened"
    assert pre_call_attrs.get("aigc.enforcement_mode") == "split", (
        f"Expected aigc.enforcement_mode='split' in span attributes; "
        f"got {pre_call_attrs}"
    )
