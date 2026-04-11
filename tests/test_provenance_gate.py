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


# ── Audit artifact provenance propagation ─────────────────────────


def test_pass_artifact_carries_provenance():
    """PASS artifact must include provenance from invocation context."""
    aigc = AIGC(custom_gates=[ProvenanceGate()])
    audit = aigc.enforce(_inv(provenance={"source_ids": ["doc-a"]}))
    assert audit["provenance"] is not None
    assert audit["provenance"]["source_ids"] == ["doc-a"]


def test_fail_artifact_carries_provenance():
    """FAIL artifact must include provenance from invocation context."""
    aigc = AIGC(custom_gates=[])  # no gate so enforcement passes; need a policy fail
    # Use a bad role to trigger a role_validation FAIL
    bad_inv = _inv(provenance={"source_ids": ["doc-a"]})
    bad_inv = {**bad_inv, "role": "nonexistent_role_xyz"}
    from aigc._internal.errors import GovernanceViolationError
    with pytest.raises(GovernanceViolationError) as exc_info:
        aigc.enforce(bad_inv)
    artifact = exc_info.value.audit_artifact
    assert artifact["provenance"] is not None
    assert artifact["provenance"]["source_ids"] == ["doc-a"]


def test_scalar_provenance_sanitized_to_none_in_artifact():
    """Scalar context.provenance must not crash artifact generation; emits null.

    ProvenanceGate(require_source_ids=False) lets scalar provenance pass the gate,
    but the artifact propagation step must sanitize it before passing to
    _normalize_provenance() (which calls .items() and would crash on a string).
    """
    aigc = AIGC(custom_gates=[ProvenanceGate(require_source_ids=False)])
    audit = aigc.enforce(_inv(provenance="bad-scalar"))
    assert audit["enforcement_result"] == "PASS"
    assert audit["provenance"] is None


def test_phase_a_split_fail_artifact_carries_provenance():
    """Phase A split-mode FAIL artifact must include provenance.

    Exercises _build_phase_a_mid_pipeline_fail_artifact() at line ~571.
    A bad role that passes policy loading but fails role validation triggers
    this path via enforce_pre_call().
    """
    from aigc import enforce_pre_call
    from aigc._internal.errors import GovernanceViolationError
    inv = {
        **_BASE,
        "role": "nonexistent_role_xyz",
        "context": {"role_declared": True, "schema_exists": True,
                    "provenance": {"source_ids": ["doc-a"]}},
    }
    with pytest.raises(GovernanceViolationError) as exc_info:
        enforce_pre_call(inv)
    artifact = exc_info.value.audit_artifact
    assert artifact["provenance"] is not None
    assert artifact["provenance"]["source_ids"] == ["doc-a"]


def test_pre_pipeline_fail_artifact_carries_provenance():
    """Pre-pipeline FAIL artifact must include provenance.

    Exercises _generate_pre_pipeline_fail_artifact() at line ~2128.
    A non-existent policy file triggers a PolicyLoadError before the
    enforcement pipeline runs.
    """
    from aigc import enforce_invocation
    from aigc import PolicyLoadError
    inv = {
        **_BASE,
        "policy_file": "nonexistent/path/policy.yaml",
        "context": {"role_declared": True, "schema_exists": True,
                    "provenance": {"source_ids": ["doc-a"]}},
    }
    with pytest.raises(PolicyLoadError) as exc_info:
        enforce_invocation(inv)
    artifact = exc_info.value.audit_artifact
    assert artifact["provenance"] is not None
    assert artifact["provenance"]["source_ids"] == ["doc-a"]


def test_split_fn_fail_artifact_carries_provenance():
    """emit_split_fn_failure_artifact must include provenance from Phase A snapshot.

    Exercises emit_split_fn_failure_artifact() at line ~2173.
    Called directly after a successful enforce_pre_call() with provenance.
    """
    from aigc._internal.enforcement import emit_split_fn_failure_artifact
    from aigc import enforce_pre_call
    inv = _inv(provenance={"source_ids": ["doc-a"]})
    pre = enforce_pre_call(inv)
    artifact = emit_split_fn_failure_artifact(pre, RuntimeError("wrapped fn failed"))
    assert artifact["provenance"] is not None
    assert artifact["provenance"]["source_ids"] == ["doc-a"]


def test_phase_b_fail_artifact_carries_provenance():
    """Phase B FAIL artifact must include provenance (enforce_post_call path).

    Exercises _run_phase_b FAIL block (site 3 in Task 2).
    enforce_pre_call succeeds, then enforce_post_call fails schema validation
    because the output is missing the required 'confidence' field.
    """
    from aigc import enforce_pre_call, enforce_post_call
    from aigc._internal.errors import SchemaValidationError
    pre = enforce_pre_call(_inv(provenance={"source_ids": ["doc-a"]}))
    with pytest.raises(SchemaValidationError) as exc_info:
        enforce_post_call(pre, {"result": "ok"})  # missing required 'confidence'
    artifact = exc_info.value.audit_artifact
    assert artifact["enforcement_result"] == "FAIL"
    assert artifact["provenance"] is not None
    assert artifact["provenance"]["source_ids"] == ["doc-a"]


# ── Bug regression: provenance normalization (Codex review findings) ──────────


def test_tuple_source_ids_normalized_to_list_in_artifact():
    """Tuple source_ids must be coerced to list so the emitted artifact is schema-valid.

    jsonschema treats Python tuples as non-arrays. _normalize_provenance must
    round-trip through JSON to ensure tuples become lists before the artifact
    is written. PASS artifacts were previously rejected by schema validators
    for this input.
    """
    import json
    from pathlib import Path
    from jsonschema import validate
    schema = json.loads(Path("schemas/audit_artifact.schema.json").read_text())
    aigc_instance = AIGC(custom_gates=[ProvenanceGate()])
    audit = aigc_instance.enforce(_inv(provenance={"source_ids": ("doc-a",)}))
    assert audit["enforcement_result"] == "PASS"
    assert audit["provenance"]["source_ids"] == ["doc-a"]  # tuple coerced to list
    validate(instance=audit, schema=schema)


def test_scalar_checksums_dropped_not_forwarded():
    """Scalar derived_from_audit_checksums must be dropped, not forwarded.

    A string where a list is required would produce a schema-invalid artifact.
    _normalize_provenance must drop the field silently rather than forward it.
    """
    aigc_instance = AIGC(custom_gates=[ProvenanceGate()])
    audit = aigc_instance.enforce(_inv(provenance={
        "source_ids": ["doc-a"],
        "derived_from_audit_checksums": "bad-not-a-list",
    }))
    assert audit["provenance"]["source_ids"] == ["doc-a"]
    assert "derived_from_audit_checksums" not in audit["provenance"]


def test_unknown_provenance_keys_dropped():
    """Unknown provenance keys must be dropped; schema has additionalProperties: false."""
    aigc_instance = AIGC(custom_gates=[ProvenanceGate()])
    audit = aigc_instance.enforce(_inv(provenance={
        "source_ids": ["doc-a"],
        "unexpected_field": "should-be-dropped",
    }))
    assert "unexpected_field" not in audit["provenance"]


def test_full_provenance_pass_artifact_schema_validates():
    """PASS artifact with all three provenance fields must validate against schema v1.4."""
    import json
    from pathlib import Path
    from jsonschema import validate
    schema = json.loads(Path("schemas/audit_artifact.schema.json").read_text())
    checksum_a = "a" * 64
    checksum_b = "b" * 64
    aigc_instance = AIGC(custom_gates=[ProvenanceGate()])
    audit = aigc_instance.enforce(_inv(provenance={
        "source_ids": ["doc-a"],
        "derived_from_audit_checksums": [checksum_a],
        "compilation_source_hash": checksum_b,
    }))
    validate(instance=audit, schema=schema)


# ── Bug regression: source_ids item validation ────────────────────


def test_fails_source_ids_contains_integer():
    """[123] passes list/non-empty check but must fail — items must be strings."""
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(provenance={"source_ids": [123]}), {}, {})
    assert result.passed is False
    assert result.failures[0]["code"] == SOURCE_IDS_MISSING


def test_fails_source_ids_contains_none():
    """[None] passes list/non-empty check but must fail — items must be strings."""
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(provenance={"source_ids": [None]}), {}, {})
    assert result.passed is False
    assert result.failures[0]["code"] == SOURCE_IDS_MISSING


def test_fails_source_ids_contains_empty_string():
    """[""] passes list/non-empty check but must fail — minLength 1 in schema."""
    gate = ProvenanceGate()
    result = gate.evaluate(_inv(provenance={"source_ids": [""]}), {}, {})
    assert result.passed is False
    assert result.failures[0]["code"] == SOURCE_IDS_MISSING


# ── Bug regression: custom gate failure message redaction ─────────


def test_custom_gate_failure_messages_are_redacted():
    """Gate failure messages must be sanitized before entering artifact failures.

    Any gate that echoes user input (PII, secrets) in its failure message must
    not leak that content into the emitted audit artifact.
    """
    from aigc._internal.gates import EnforcementGate, GateResult, INSERTION_PRE_OUTPUT as IPO

    class LeakyGate(EnforcementGate):
        @property
        def name(self):
            return "leaky_gate"

        @property
        def insertion_point(self):
            return IPO

        def evaluate(self, invocation, policy, context):
            prompt = invocation.get("input", {}).get("prompt", "")
            return GateResult(
                passed=False,
                failures=[{"code": "LEAKY", "message": f"rejected: {prompt}", "field": None}],
            )

    aigc_instance = AIGC(custom_gates=[LeakyGate()])
    pii_inv = {**_inv(), "input": {"prompt": "contact user@example.com please"}}
    with pytest.raises(CustomGateViolationError) as exc_info:
        aigc_instance.enforce(pii_inv)
    artifact = exc_info.value.audit_artifact
    assert "user@example.com" not in artifact["failures"][0]["message"]
    assert "[REDACTED:email]" in artifact["failures"][0]["message"]


# ── Public API ────────────────────────────────────────────────────


def test_public_import():
    from aigc import ProvenanceGate as PG  # noqa: F401
    assert PG is ProvenanceGate


def test_public_failure_codes_importable():
    from aigc.provenance_gate import PROVENANCE_MISSING as PM, SOURCE_IDS_MISSING as SIM
    assert PM == "PROVENANCE_MISSING"
    assert SIM == "SOURCE_IDS_MISSING"
