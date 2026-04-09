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


def test_provenance_invalid_value_passes_through():
    """Invalid value passes through unchanged; schema validation owns correctness."""
    artifact = _make_artifact(provenance={"source_ids": "bad-not-a-list"})
    assert artifact["provenance"] == {"source_ids": "bad-not-a-list"}


def test_audit_schema_version_is_1_4():
    """Artifact emits audit_schema_version 1.4."""
    artifact = _make_artifact()
    assert artifact["audit_schema_version"] == "1.4"
