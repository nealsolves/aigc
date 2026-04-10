"""
Tests for audit artifact v1.4 provenance metadata fields.

Verifies:
- generate_audit_artifact() emits "provenance": None by default
- _normalize_provenance() behavior (via generate_audit_artifact)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aigc._internal.audit import generate_audit_artifact

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "audit_artifact.schema.json"
CHECKSUM_A = "a" * 64
CHECKSUM_B = "b" * 64


# Used by schema validation tests added in Task 4 (test_artifact_with_full_provenance_validates, etc.)
@pytest.fixture(scope="module")
def audit_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _minimal_invocation() -> dict:
    return {
        "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
        "model_provider": "test_provider",
        "model_identifier": "test_model",
        "role": "tester",
        "input": {},
        "output": {},
        "context": {},
    }


def _minimal_policy() -> dict:
    return {"policy_version": "1.0"}


def _make_artifact(provenance=None) -> dict:
    return generate_audit_artifact(
        _minimal_invocation(),
        _minimal_policy(),
        provenance=provenance,
        timestamp=1700000000,
    )


def _inject_provenance(provenance_value) -> dict:
    """Build a schema-valid artifact then directly set provenance, bypassing normalization."""
    artifact = _make_artifact()
    artifact["provenance"] = provenance_value
    return artifact


def test_provenance_absent_emits_null():
    """Default: no provenance kwarg → artifact has "provenance": None."""
    artifact = generate_audit_artifact(
        _minimal_invocation(),
        _minimal_policy(),
        timestamp=1700000000,
    )
    assert "provenance" in artifact
    assert artifact["provenance"] is None


def test_provenance_none_kwarg_emits_null():
    """Explicit provenance=None → artifact has "provenance": None."""
    artifact = _make_artifact(provenance=None)
    assert artifact["provenance"] is None


def test_provenance_empty_dict_emits_null():
    """Empty dict normalizes to None."""
    artifact = _make_artifact(provenance={})
    assert artifact["provenance"] is None


def test_provenance_all_none_values_emits_null():
    """Dict with all-None values normalizes to None."""
    artifact = _make_artifact(provenance={
        "source_ids": None,
        "compilation_source_hash": None,
    })
    assert artifact["provenance"] is None


def test_provenance_full_object_emitted():
    """All three keys present → object with all three keys."""
    prov = {
        "source_ids": ["step-1", "step-2"],
        "derived_from_audit_checksums": [CHECKSUM_A],
        "compilation_source_hash": CHECKSUM_B,
    }
    artifact = _make_artifact(provenance=prov)
    assert artifact["provenance"] == prov


def test_provenance_sparse_only_provided_keys():
    """Only source_ids supplied → only source_ids in artifact provenance."""
    artifact = _make_artifact(provenance={"source_ids": ["step-1"]})
    assert artifact["provenance"] == {"source_ids": ["step-1"]}
    assert "derived_from_audit_checksums" not in artifact["provenance"]
    assert "compilation_source_hash" not in artifact["provenance"]


def test_provenance_none_value_pruned_other_key_kept():
    """None value for one key pruned; other key kept."""
    artifact = _make_artifact(provenance={
        "source_ids": ["step-1"],
        "compilation_source_hash": None,
    })
    assert artifact["provenance"] == {"source_ids": ["step-1"]}


def test_provenance_list_field_scalar_dropped():
    """Scalar in a list field is dropped, not forwarded, to keep artifacts schema-valid.

    Previously values passed through unchanged (schema validation owned correctness).
    Now scalars in array-typed fields are dropped at normalization so enforcement
    never emits a schema-invalid artifact.
    """
    artifact = _make_artifact(provenance={"source_ids": "bad-not-a-list"})
    assert artifact["provenance"] is None


def test_non_json_serializable_provenance_raises():
    """Non-JSON-serializable values inside a list raise ValueError before the artifact is built.

    A bare set for source_ids is now dropped at normalization time (not a list/tuple).
    But a set *inside* a list passes the isinstance check and must still raise
    ValueError at the json.dumps step rather than crash later at signing time.
    """
    with pytest.raises(ValueError, match="non-JSON-serializable"):
        _make_artifact(provenance={"source_ids": [{"not-a-string-but-a-set"}]})


def test_audit_schema_version_is_1_4():
    """Artifact emits audit_schema_version 1.4."""
    artifact = _make_artifact()
    assert artifact["audit_schema_version"] == "1.4"


def test_artifact_with_full_provenance_validates(audit_schema: dict):
    """Full provenance object validates against schema v1.4."""
    from jsonschema import validate
    artifact = _make_artifact(provenance={
        "source_ids": ["step-1"],
        "derived_from_audit_checksums": [CHECKSUM_A],
        "compilation_source_hash": CHECKSUM_B,
    })
    validate(instance=artifact, schema=audit_schema)


def test_artifact_without_provenance_key_validates(audit_schema: dict):
    """v1.3-era artifact (no provenance key) validates under v1.4 schema."""
    from jsonschema import validate
    artifact = _make_artifact()
    del artifact["provenance"]
    validate(instance=artifact, schema=audit_schema)


def test_artifact_with_null_provenance_validates(audit_schema: dict):
    """provenance: null is schema-valid."""
    from jsonschema import validate
    artifact = _make_artifact()
    assert artifact["provenance"] is None
    validate(instance=artifact, schema=audit_schema)


def test_schema_rejects_empty_source_ids(audit_schema: dict):
    """The schema itself rejects provenance.source_ids: [] (minItems: 1)."""
    from jsonschema import validate, ValidationError
    artifact = _inject_provenance({"source_ids": []})
    with pytest.raises(ValidationError):
        validate(instance=artifact, schema=audit_schema)


def test_schema_rejects_empty_checksums(audit_schema: dict):
    """The schema itself rejects derived_from_audit_checksums: [] (minItems: 1)."""
    from jsonschema import validate, ValidationError
    artifact = _inject_provenance({"derived_from_audit_checksums": []})
    with pytest.raises(ValidationError):
        validate(instance=artifact, schema=audit_schema)


def test_schema_rejects_bad_checksum_pattern(audit_schema: dict):
    """The schema itself rejects non-hex64 entries in checksums."""
    from jsonschema import validate, ValidationError
    artifact = _inject_provenance({"derived_from_audit_checksums": ["not-a-sha256-hash"]})
    with pytest.raises(ValidationError):
        validate(instance=artifact, schema=audit_schema)


def test_schema_rejects_bad_compilation_hash(audit_schema: dict):
    """The schema itself rejects a non-hex64 compilation_source_hash."""
    from jsonschema import validate, ValidationError
    artifact = _inject_provenance({"compilation_source_hash": "not-a-sha256"})
    with pytest.raises(ValidationError):
        validate(instance=artifact, schema=audit_schema)


def test_schema_rejects_duplicate_source_ids(audit_schema: dict):
    """The schema itself rejects duplicate source_ids (uniqueItems: true)."""
    from jsonschema import validate, ValidationError
    artifact = _inject_provenance({"source_ids": ["a", "a"]})
    with pytest.raises(ValidationError):
        validate(instance=artifact, schema=audit_schema)


def test_schema_rejects_duplicate_checksums(audit_schema: dict):
    """The schema itself rejects duplicate checksums (uniqueItems: true)."""
    from jsonschema import validate, ValidationError
    valid = "d" * 64
    artifact = _inject_provenance({"derived_from_audit_checksums": [valid, valid]})
    with pytest.raises(ValidationError):
        validate(instance=artifact, schema=audit_schema)


def test_schema_rejects_too_many_source_ids(audit_schema: dict):
    """The schema itself rejects source_ids lists longer than 1000 items."""
    from jsonschema import validate, ValidationError
    big_list = [f"id-{i}" for i in range(1001)]
    artifact = _inject_provenance({"source_ids": big_list})
    with pytest.raises(ValidationError):
        validate(instance=artifact, schema=audit_schema)


def test_schema_rejects_too_many_checksums(audit_schema: dict):
    """The schema itself rejects checksum lists longer than 1000 items."""
    from jsonschema import validate, ValidationError
    big_list = [f"{i:064x}" for i in range(1001)]
    artifact = _inject_provenance({"derived_from_audit_checksums": big_list})
    with pytest.raises(ValidationError):
        validate(instance=artifact, schema=audit_schema)


def test_nan_in_provenance_raises_value_error():
    """NaN in provenance values raises ValueError before the artifact is built.

    json.dumps() silently allows NaN by default, but canonical_json_bytes()
    (used at signing time) rejects it with allow_nan=False.  _normalize_provenance
    must reject NaN at call time rather than deferring the crash to sign_artifact().
    """
    from math import nan
    with pytest.raises(ValueError, match="non-JSON-serializable"):
        _make_artifact(provenance={"source_ids": [nan]})


# ── Normalizer item-level hardening ──────────────────────────────────────────

def test_normalizer_drops_empty_source_ids():
    """source_ids: [] → empty after no-op filter → provenance: null."""
    assert _make_artifact(provenance={"source_ids": []})["provenance"] is None


def test_normalizer_drops_all_nonstring_source_ids():
    """source_ids: [123] → non-string filtered → provenance: null."""
    assert _make_artifact(provenance={"source_ids": [123]})["provenance"] is None


def test_normalizer_filters_mixed_source_ids():
    """source_ids with mixed valid/invalid → only non-empty strings kept."""
    artifact = _make_artifact(provenance={"source_ids": [123, "valid", "", "also-valid"]})
    assert artifact["provenance"] == {"source_ids": ["valid", "also-valid"]}


def test_normalizer_drops_empty_string_source_ids():
    """source_ids: [""] → minLength:1 filtering → provenance: null."""
    assert _make_artifact(provenance={"source_ids": [""]})["provenance"] is None


def test_normalizer_deduplicates_source_ids():
    """Duplicate source_ids entries → first occurrence kept."""
    artifact = _make_artifact(provenance={"source_ids": ["a", "b", "a"]})
    assert artifact["provenance"] == {"source_ids": ["a", "b"]}


def test_normalizer_drops_empty_checksums():
    """derived_from_audit_checksums: [] → provenance: null."""
    assert _make_artifact(provenance={"derived_from_audit_checksums": []})["provenance"] is None


def test_normalizer_filters_invalid_checksum_patterns():
    """Non-hex64 checksum items filtered; field dropped when none remain."""
    assert _make_artifact(
        provenance={"derived_from_audit_checksums": ["not-a-hash"]}
    )["provenance"] is None


def test_normalizer_keeps_valid_checksums():
    """Valid hex64 checksums pass through unchanged."""
    valid = "a" * 64
    artifact = _make_artifact(provenance={"derived_from_audit_checksums": [valid]})
    assert artifact["provenance"] == {"derived_from_audit_checksums": [valid]}


def test_normalizer_deduplicates_checksums():
    """Duplicate hex64 checksums → first occurrence kept."""
    valid = "b" * 64
    artifact = _make_artifact(provenance={"derived_from_audit_checksums": [valid, valid]})
    assert artifact["provenance"] == {"derived_from_audit_checksums": [valid]}


def test_normalizer_drops_nonstring_compilation_hash():
    """compilation_source_hash: 123 → not a string → provenance: null."""
    assert _make_artifact(provenance={"compilation_source_hash": 123})["provenance"] is None


def test_normalizer_drops_invalid_compilation_hash_pattern():
    """compilation_source_hash: 'bad' → fails hex64 pattern → provenance: null."""
    assert _make_artifact(provenance={"compilation_source_hash": "not-hex64"})["provenance"] is None


def test_normalizer_valid_compilation_hash_passes():
    """Valid 64-char lowercase hex compilation_source_hash passes through."""
    valid = "c" * 64
    artifact = _make_artifact(provenance={"compilation_source_hash": valid})
    assert artifact["provenance"] == {"compilation_source_hash": valid}


def test_normalizer_truncates_source_ids_at_max_items():
    """source_ids with 1001 valid items → truncated to 1000."""
    big_list = [f"id-{i}" for i in range(1001)]
    artifact = _make_artifact(provenance={"source_ids": big_list})
    assert len(artifact["provenance"]["source_ids"]) == 1000
    assert artifact["provenance"]["source_ids"][0] == "id-0"
    assert artifact["provenance"]["source_ids"][-1] == "id-999"


def test_normalizer_truncates_checksums_at_max_items():
    """checksums with 1001 valid unique entries → truncated to 1000."""
    big_list = [f"{i:064x}" for i in range(1001)]
    artifact = _make_artifact(provenance={"derived_from_audit_checksums": big_list})
    assert len(artifact["provenance"]["derived_from_audit_checksums"]) == 1000
    assert artifact["provenance"]["derived_from_audit_checksums"][0] == f"{0:064x}"
    assert artifact["provenance"]["derived_from_audit_checksums"][-1] == f"{999:064x}"


def test_non_json_serializable_compilation_hash_still_raises():
    """Non-serializable compilation_source_hash still raises ValueError."""
    with pytest.raises(ValueError, match="non-JSON-serializable"):
        _make_artifact(provenance={"compilation_source_hash": {"not-a-string-but-a-set"}})


def test_normalizer_empty_source_ids_artifact_is_schema_valid(audit_schema):
    """After hardening: source_ids=[] → provenance=null → artifact passes schema."""
    from jsonschema import validate
    artifact = _make_artifact(provenance={"source_ids": []})
    assert artifact["provenance"] is None
    validate(instance=artifact, schema=audit_schema)  # must not raise
