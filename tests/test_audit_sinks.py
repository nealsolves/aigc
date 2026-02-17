"""
Phase 3.2 — Audit sink tests.

Tests: both sink types, sink failure isolation, no-sink default,
set/clear, and that FAIL artifacts are also emitted to the sink.
"""

from __future__ import annotations

import json

import pytest

from src.enforcement import enforce_invocation
from src.errors import GovernanceViolationError
from src.sinks import (
    AuditSink,
    CallbackAuditSink,
    JsonFileAuditSink,
    emit_to_sink,
    get_audit_sink,
    set_audit_sink,
)

POLICY = "tests/golden_traces/golden_policy_v1.yaml"

VALID_INVOCATION = {
    "policy_file": POLICY,
    "model_provider": "anthropic",
    "model_identifier": "claude-sonnet-4-5-20250929",
    "role": "planner",
    "input": {"task": "analyse"},
    "output": {"result": "ok", "confidence": 0.9},
    "context": {"role_declared": True, "schema_exists": True},
}


@pytest.fixture(autouse=True)
def clear_sink():
    """Ensure no sink bleeds between tests."""
    set_audit_sink(None)
    yield
    set_audit_sink(None)


# --- CallbackAuditSink ---

def test_callback_sink_called_on_pass():
    received = []
    set_audit_sink(CallbackAuditSink(received.append))

    enforce_invocation(VALID_INVOCATION)

    assert len(received) == 1
    assert received[0]["enforcement_result"] == "PASS"


def test_callback_sink_called_on_fail():
    received = []
    set_audit_sink(CallbackAuditSink(received.append))

    bad = {**VALID_INVOCATION, "role": "attacker"}
    with pytest.raises(GovernanceViolationError):
        enforce_invocation(bad)

    assert len(received) == 1
    assert received[0]["enforcement_result"] == "FAIL"


def test_callback_sink_receives_complete_artifact():
    received = []
    set_audit_sink(CallbackAuditSink(received.append))

    enforce_invocation(VALID_INVOCATION)

    artifact = received[0]
    for field in ("enforcement_result", "policy_file", "role", "input_checksum", "output_checksum"):
        assert field in artifact, f"Missing field: {field}"


# --- JsonFileAuditSink ---

def test_json_file_sink_writes_jsonl(tmp_path):
    sink_file = tmp_path / "audit.jsonl"
    set_audit_sink(JsonFileAuditSink(sink_file))

    enforce_invocation(VALID_INVOCATION)

    lines = sink_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    artifact = json.loads(lines[0])
    assert artifact["enforcement_result"] == "PASS"


def test_json_file_sink_appends_multiple(tmp_path):
    sink_file = tmp_path / "audit.jsonl"
    set_audit_sink(JsonFileAuditSink(sink_file))

    enforce_invocation(VALID_INVOCATION)
    enforce_invocation(VALID_INVOCATION)

    lines = sink_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_json_file_sink_fail_artifact_appended(tmp_path):
    sink_file = tmp_path / "audit.jsonl"
    set_audit_sink(JsonFileAuditSink(sink_file))

    bad = {**VALID_INVOCATION, "role": "attacker"}
    with pytest.raises(GovernanceViolationError):
        enforce_invocation(bad)

    lines = sink_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    artifact = json.loads(lines[0])
    assert artifact["enforcement_result"] == "FAIL"


# --- Sink failure isolation ---

class _BrokenSink(AuditSink):
    def emit(self, artifact):
        raise RuntimeError("sink exploded")


def test_sink_failure_does_not_propagate():
    set_audit_sink(_BrokenSink())

    # Enforcement must succeed even if the sink raises
    audit = enforce_invocation(VALID_INVOCATION)
    assert audit["enforcement_result"] == "PASS"


def test_sink_failure_on_fail_does_not_mask_exception():
    set_audit_sink(_BrokenSink())

    bad = {**VALID_INVOCATION, "role": "attacker"}
    with pytest.raises(GovernanceViolationError):
        enforce_invocation(bad)


# --- No sink (default) ---

def test_no_sink_registered_by_default():
    assert get_audit_sink() is None


def test_no_sink_enforcement_returns_normally():
    audit = enforce_invocation(VALID_INVOCATION)
    assert audit["enforcement_result"] == "PASS"


# --- set/clear ---

def test_set_then_clear_sink():
    received = []
    set_audit_sink(CallbackAuditSink(received.append))
    assert get_audit_sink() is not None

    set_audit_sink(None)
    assert get_audit_sink() is None

    enforce_invocation(VALID_INVOCATION)
    assert len(received) == 0


# --- emit_to_sink standalone ---

def test_emit_to_sink_no_op_when_no_sink():
    emit_to_sink({"enforcement_result": "PASS"})  # must not raise
