"""
Phase 3.2 — Audit sink tests.

Tests: both sink types, sink failure isolation, no-sink default,
set/clear, and that FAIL artifacts are also emitted to the sink.
"""

from __future__ import annotations

import json

import pytest

from aigc._internal.enforcement import enforce_invocation
from aigc._internal.errors import GovernanceViolationError
from aigc._internal.errors import AuditSinkError
from aigc._internal.sinks import (
    AuditSink,
    CallbackAuditSink,
    JsonFileAuditSink,
    emit_to_sink,
    get_audit_sink,
    set_audit_sink,
    set_sink_failure_mode,
    get_sink_failure_mode,
)

POLICY = "tests/golden_replays/golden_policy_v1.yaml"

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
    set_sink_failure_mode("log")
    yield
    set_audit_sink(None)
    set_sink_failure_mode("log")


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


# --- Sink failure modes (D-02 completion) ---

def test_sink_failure_mode_raise_propagates():
    """In 'raise' mode, sink failures propagate as AuditSinkError."""
    set_audit_sink(_BrokenSink())
    set_sink_failure_mode("raise")

    with pytest.raises(AuditSinkError, match="sink exploded"):
        enforce_invocation(VALID_INVOCATION)


def test_sink_failure_mode_log_does_not_propagate():
    """In 'log' mode, sink failures are logged but not propagated (default)."""
    set_audit_sink(_BrokenSink())
    set_sink_failure_mode("log")

    audit = enforce_invocation(VALID_INVOCATION)
    assert audit["enforcement_result"] == "PASS"


def test_sink_failure_mode_invalid_raises_valueerror():
    """Invalid failure mode raises ValueError."""
    with pytest.raises(ValueError, match="Invalid sink failure mode"):
        set_sink_failure_mode("invalid")


def test_sink_failure_mode_default_is_log():
    """Default failure mode is 'log'."""
    assert get_sink_failure_mode() == "log"


def test_audit_sink_error_has_correct_code():
    """AuditSinkError has the correct error code."""
    err = AuditSinkError("test")
    assert err.code == "AUDIT_SINK_ERROR"


# --- CR-02: Sink isolation in AIGC class ---

def test_aigc_instance_does_not_mutate_global_sink():
    """AIGC.enforce() must never touch the global sink state."""
    from aigc import AIGC

    assert get_audit_sink() is None  # no prior sink
    received = []
    aigc = AIGC(sink=CallbackAuditSink(received.append))
    aigc.enforce(VALID_INVOCATION)

    assert len(received) == 1
    # Global sink must remain untouched — AIGC uses per-call sink injection
    assert get_audit_sink() is None


def test_aigc_instance_does_not_leak_to_global_with_previous():
    """AIGC.enforce() must not affect a previously set global sink."""
    from aigc import AIGC

    previous_received = []
    previous_sink = CallbackAuditSink(previous_received.append)
    set_audit_sink(previous_sink)

    instance_received = []
    aigc = AIGC(sink=CallbackAuditSink(instance_received.append))
    aigc.enforce(VALID_INVOCATION)

    assert len(instance_received) == 1
    # Previous global sink must remain unchanged and not have received anything
    assert get_audit_sink() is previous_sink
    assert len(previous_received) == 0


def test_aigc_two_instances_isolated():
    """Two AIGC instances with different sinks must not interfere."""
    from aigc import AIGC

    received_a = []
    received_b = []
    aigc_a = AIGC(sink=CallbackAuditSink(received_a.append))
    aigc_b = AIGC(sink=CallbackAuditSink(received_b.append))

    aigc_a.enforce(VALID_INVOCATION)
    aigc_b.enforce(VALID_INVOCATION)

    assert len(received_a) == 1
    assert len(received_b) == 1
    # Each sink received only its own instance's artifact
    assert received_a[0] is not received_b[0]


def test_aigc_instance_with_none_sink_does_not_interfere():
    """AIGC(sink=None) must not receive artifacts from another instance."""
    from aigc import AIGC

    received = []
    aigc_sinked = AIGC(sink=CallbackAuditSink(received.append))
    aigc_none = AIGC()

    aigc_none.enforce(VALID_INVOCATION)
    aigc_sinked.enforce(VALID_INVOCATION)

    # Only the sinked instance's sink should have received an artifact
    assert len(received) == 1


# --- CR-03: on_sink_failure wired into runtime ---

def test_aigc_on_sink_failure_raise_is_effective():
    """AIGC(on_sink_failure='raise') must actually raise on PASS sink failure."""
    from aigc import AIGC

    aigc = AIGC(sink=_BrokenSink(), on_sink_failure="raise")
    with pytest.raises(AuditSinkError, match="sink exploded"):
        aigc.enforce(VALID_INVOCATION)


def test_aigc_on_sink_failure_log_does_not_raise():
    """AIGC(on_sink_failure='log') must not raise on sink failure."""
    from aigc import AIGC

    aigc = AIGC(sink=_BrokenSink(), on_sink_failure="log")
    audit = aigc.enforce(VALID_INVOCATION)
    assert audit["enforcement_result"] == "PASS"


def test_aigc_does_not_mutate_global_failure_mode():
    """AIGC.enforce() must never touch the global failure mode."""
    from aigc import AIGC

    assert get_sink_failure_mode() == "log"  # default
    aigc = AIGC(sink=CallbackAuditSink(lambda a: None), on_sink_failure="raise")
    aigc.enforce(VALID_INVOCATION)
    assert get_sink_failure_mode() == "log"  # untouched


# --- CR-03: Artifact immutability across sink boundary ---

class _MutatingSink(AuditSink):
    """Sink that attempts to mutate the artifact."""
    def emit(self, artifact):
        artifact["enforcement_result"] = "MUTATED"
        artifact["metadata"]["tampered"] = True


def test_sink_cannot_mutate_caller_artifact():
    """Sink receives a deep copy; mutations must not affect the caller's artifact."""
    set_audit_sink(_MutatingSink())

    audit = enforce_invocation(VALID_INVOCATION)
    assert audit["enforcement_result"] == "PASS"
    assert "tampered" not in audit.get("metadata", {})


def test_sink_cannot_mutate_exception_artifact():
    """Sink mutations must not affect the artifact attached to governance exceptions."""
    set_audit_sink(_MutatingSink())

    bad = {**VALID_INVOCATION, "role": "attacker"}
    with pytest.raises(GovernanceViolationError) as exc_info:
        enforce_invocation(bad)

    assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"
    assert "tampered" not in exc_info.value.audit_artifact.get("metadata", {})


def test_aigc_sink_cannot_mutate_artifact():
    """AIGC instance sink receives a deep copy."""
    from aigc import AIGC

    aigc = AIGC(sink=_MutatingSink())
    audit = aigc.enforce(VALID_INVOCATION)
    assert audit["enforcement_result"] == "PASS"


# --- CR-04: FAIL artifact preserved when sink raises ---

def test_fail_artifact_preserved_when_sink_raises():
    """On FAIL path, governance exception must propagate even if sink raises."""
    set_audit_sink(_BrokenSink())
    set_sink_failure_mode("raise")

    bad = {**VALID_INVOCATION, "role": "attacker"}
    with pytest.raises(GovernanceViolationError) as exc_info:
        enforce_invocation(bad)

    # The governance exception must have the audit artifact attached
    assert hasattr(exc_info.value, "audit_artifact")
    assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"


def test_fail_artifact_preserved_via_aigc_instance():
    """AIGC(on_sink_failure='raise') must preserve FAIL artifact on sink error."""
    from aigc import AIGC

    aigc = AIGC(sink=_BrokenSink(), on_sink_failure="raise")
    bad = {**VALID_INVOCATION, "role": "attacker"}
    with pytest.raises(GovernanceViolationError) as exc_info:
        aigc.enforce(bad)

    assert hasattr(exc_info.value, "audit_artifact")
    assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"


# --- CR-04: Pre-pipeline FAIL artifact generation ---

def test_pre_pipeline_invocation_validation_has_artifact():
    """InvocationValidationError must carry a FAIL audit artifact."""
    from aigc._internal.errors import InvocationValidationError

    bad = {**VALID_INVOCATION}
    del bad["role"]  # missing required field
    with pytest.raises(InvocationValidationError) as exc_info:
        enforce_invocation(bad)

    assert exc_info.value.audit_artifact is not None
    assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"
    assert exc_info.value.audit_artifact["failure_gate"] == "invocation_validation"


def test_pre_pipeline_policy_load_error_has_artifact():
    """PolicyLoadError must carry a FAIL audit artifact."""
    from aigc._internal.errors import PolicyLoadError

    bad = {**VALID_INVOCATION, "policy_file": "nonexistent_policy.yaml"}
    with pytest.raises(PolicyLoadError) as exc_info:
        enforce_invocation(bad)

    assert exc_info.value.audit_artifact is not None
    assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"
    assert exc_info.value.audit_artifact["failure_gate"] == "invocation_validation"


def test_pre_pipeline_aigc_strict_mode_has_artifact():
    """Strict mode PolicyValidationError must carry a FAIL audit artifact."""
    from aigc import AIGC
    from aigc._internal.errors import PolicyValidationError

    aigc = AIGC(strict_mode=True)
    with pytest.raises(PolicyValidationError) as exc_info:
        aigc.enforce(VALID_INVOCATION)

    assert exc_info.value.audit_artifact is not None
    assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"


# --- CR-05: Sink failure gate mapping ---

def test_sink_failure_gate_is_schema_valid():
    """AuditSinkError must map to 'sink_emission' gate (schema-valid)."""
    from aigc._internal.enforcement import _map_exception_to_failure_gate

    exc = AuditSinkError("test")
    assert _map_exception_to_failure_gate(exc) == "sink_emission"


# --- CR-06: PolicyCache wired into AIGC ---

def test_aigc_has_policy_cache():
    """AIGC instances must have a per-instance PolicyCache."""
    from aigc import AIGC

    aigc = AIGC()
    assert hasattr(aigc, 'policy_cache')
    assert aigc.policy_cache is not None


def test_aigc_policy_cache_is_per_instance():
    """Two AIGC instances must have separate PolicyCache instances."""
    from aigc import AIGC

    a = AIGC()
    b = AIGC()
    assert a.policy_cache is not b.policy_cache
