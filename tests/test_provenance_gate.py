"""Tests for the built-in ProvenanceGate enforcement gate."""
import pytest

from aigc._internal.gates import INSERTION_PRE_OUTPUT
from aigc._internal.provenance_gate import (
    ProvenanceGate,
    PROVENANCE_MISSING,
    SOURCE_IDS_MISSING,
)
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import CustomGateViolationError

# ── Invocation fixtures ────────────────────────────────────────────

_BASE = {
    "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "planner",
    "input": {"prompt": "test"},
    "output": {"result": "ok", "confidence": 0.9},
}

# Sentinel so _inv() and _inv(None) are distinguishable.
_ABSENT = object()


def _inv(provenance=_ABSENT):
    """Build a valid invocation. Pass provenance=None to set key to None explicitly."""
    ctx = {"role_declared": True, "schema_exists": True}
    if provenance is not _ABSENT:
        ctx["provenance"] = provenance
    return {**_BASE, "context": ctx}


# ── Unit: construction ─────────────────────────────────────────────


def test_gate_instantiates_with_defaults():
    gate = ProvenanceGate()
    assert gate.name == "provenance_gate"
    assert gate.insertion_point == INSERTION_PRE_OUTPUT


def test_gate_insertion_point_is_pre_output():
    assert ProvenanceGate().insertion_point == INSERTION_PRE_OUTPUT


# ── Unit: passes ──────────────────────────────────────────────────


def test_passes_with_source_ids():
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(provenance={"source_ids": ["step-1"]}), {}, {})
    assert result.passed is True
    assert result.failures == []


def test_passes_when_require_source_ids_false_and_provenance_absent():
    gate = ProvenanceGate(require_source_ids=False)
    result = gate.evaluate(_inv(), {}, {})
    assert result.passed is True


def test_passes_when_require_source_ids_false_even_with_bad_provenance():
    gate = ProvenanceGate(require_source_ids=False)
    result = gate.evaluate(_inv(provenance="bad_scalar"), {}, {})
    assert result.passed is True


# ── Unit: PROVENANCE_MISSING failures ─────────────────────────────


def test_fails_provenance_key_absent():
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(), {}, {})  # no provenance key at all
    assert result.passed is False
    assert result.failures[0]["code"] == PROVENANCE_MISSING
    assert result.failures[0]["field"] == "context.provenance"


def test_fails_provenance_explicit_none():
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(provenance=None), {}, {})  # key present, value None
    assert result.passed is False
    assert result.failures[0]["code"] == PROVENANCE_MISSING


def test_fails_provenance_empty_dict():
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(provenance={}), {}, {})
    assert result.passed is False
    assert result.failures[0]["code"] == PROVENANCE_MISSING


def test_fails_provenance_scalar_string():
    """Scalar provenance (non-Mapping) must not crash — yields PROVENANCE_MISSING."""
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(provenance="step-1"), {}, {})
    assert result.passed is False
    assert result.failures[0]["code"] == PROVENANCE_MISSING


# ── Unit: SOURCE_IDS_MISSING failures ─────────────────────────────


def test_fails_source_ids_empty_list():
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(provenance={"source_ids": []}), {}, {})
    assert result.passed is False
    assert result.failures[0]["code"] == SOURCE_IDS_MISSING
    assert result.failures[0]["field"] == "context.provenance.source_ids"


def test_fails_source_ids_key_absent():
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(provenance={"compilation_source_hash": "abc"}), {}, {})
    assert result.passed is False
    assert result.failures[0]["code"] == SOURCE_IDS_MISSING


def test_fails_source_ids_is_string_not_list():
    """source_ids must be a list/sequence — bare string must not pass."""
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(provenance={"source_ids": "step-1"}), {}, {})
    assert result.passed is False
    assert result.failures[0]["code"] == SOURCE_IDS_MISSING


# ── Integration: AIGC pipeline ────────────────────────────────────


def test_aigc_with_provenance_gate_passes():
    aigc = AIGC(custom_gates=[ProvenanceGate()])
    audit = aigc.enforce(_inv(provenance={"source_ids": ["step-1"]}))
    assert audit["enforcement_result"] == "PASS"
    assert "custom:provenance_gate" in audit["metadata"]["gates_evaluated"]


def test_aigc_with_provenance_gate_fails_no_provenance():
    aigc = AIGC(custom_gates=[ProvenanceGate()])
    with pytest.raises(CustomGateViolationError) as exc_info:
        aigc.enforce(_inv())
    artifact = exc_info.value.audit_artifact
    assert artifact["failure_gate"] == "custom_gate_violation"
    # FAIL artifacts store failures at top level, not under metadata
    assert any(f["code"] == PROVENANCE_MISSING for f in artifact["failures"])


def test_aigc_with_provenance_gate_fails_source_ids_missing():
    aigc = AIGC(custom_gates=[ProvenanceGate()])
    with pytest.raises(CustomGateViolationError) as exc_info:
        aigc.enforce(_inv(provenance={"compilation_source_hash": "abc"}))
    artifact = exc_info.value.audit_artifact
    assert any(f["code"] == SOURCE_IDS_MISSING for f in artifact["failures"])
