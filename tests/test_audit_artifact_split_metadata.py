"""
Tests for audit artifact v1.3 split-enforcement metadata fields.

Verifies that:
- AUDIT_SCHEMA_VERSION is "1.3"
- The audit artifact JSON schema accepts the new optional split metadata
  properties (enforcement_mode, pre_call_gates_evaluated,
  post_call_gates_evaluated, pre_call_timestamp, post_call_timestamp)
- The schema rejects invalid values for enforcement_mode
- Legacy v1.2 metadata keys still validate without modification
  (backward compatibility)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import validate, ValidationError

from aigc._internal.audit import generate_audit_artifact, AUDIT_SCHEMA_VERSION

# ── Fixtures ──────────────────────────────────────────────────────────────────

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "audit_artifact.schema.json"


@pytest.fixture(scope="module")
def audit_schema() -> dict:
    """Load the audit artifact JSON schema once per module."""
    return json.loads(SCHEMA_PATH.read_text())


def _minimal_invocation() -> dict:
    """Minimal valid invocation accepted by generate_audit_artifact."""
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


def _make_artifact(metadata: dict | None = None) -> dict:
    """Generate an audit artifact with the given metadata."""
    return generate_audit_artifact(
        _minimal_invocation(),
        _minimal_policy(),
        metadata=metadata,
        timestamp=1700000000,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_schema_version_is_1_3() -> None:
    """AUDIT_SCHEMA_VERSION constant and generated artifact must be '1.3'."""
    assert AUDIT_SCHEMA_VERSION == "1.3"
    artifact = _make_artifact()
    assert artifact["audit_schema_version"] == "1.3"


def test_enforcement_mode_unified_valid(audit_schema: dict) -> None:
    """metadata.enforcement_mode='unified' must validate against the schema."""
    artifact = _make_artifact(metadata={"enforcement_mode": "unified"})
    validate(instance=artifact, schema=audit_schema)


def test_enforcement_mode_split_valid(audit_schema: dict) -> None:
    """metadata.enforcement_mode='split' must validate against the schema."""
    artifact = _make_artifact(metadata={"enforcement_mode": "split"})
    validate(instance=artifact, schema=audit_schema)


def test_enforcement_mode_split_pre_call_only_valid(audit_schema: dict) -> None:
    """metadata.enforcement_mode='split_pre_call_only' must validate against the schema."""
    artifact = _make_artifact(metadata={"enforcement_mode": "split_pre_call_only"})
    validate(instance=artifact, schema=audit_schema)


def test_enforcement_mode_invalid_rejected(audit_schema: dict) -> None:
    """metadata.enforcement_mode with an unrecognised value must fail validation."""
    artifact = _make_artifact(metadata={"enforcement_mode": "invalid_value"})
    with pytest.raises(ValidationError):
        validate(instance=artifact, schema=audit_schema)


def test_pre_call_gates_evaluated_valid(audit_schema: dict) -> None:
    """metadata.pre_call_gates_evaluated with a list of strings must validate."""
    artifact = _make_artifact(
        metadata={
            "pre_call_gates_evaluated": ["guard_evaluation", "role_validation"],
        }
    )
    validate(instance=artifact, schema=audit_schema)


def test_split_timestamps_valid(audit_schema: dict) -> None:
    """metadata pre_call_timestamp and post_call_timestamp must validate."""
    artifact = _make_artifact(
        metadata={
            "pre_call_timestamp": 1234567890,
            "post_call_timestamp": 1234567900,
        }
    )
    validate(instance=artifact, schema=audit_schema)


def test_legacy_metadata_still_valid(audit_schema: dict) -> None:
    """Existing v1.2 metadata keys must still validate without enforcement_mode.

    This proves backward compatibility: artifacts produced before the
    split-enforcement feature was introduced continue to pass schema validation.
    """
    legacy_metadata = {
        "gates_evaluated": ["role_validation", "precondition_validation"],
        "preconditions_satisfied": ["role_declared", "schema_exists"],
        "schema_validation": "passed",
        "risk_scoring": {"mode": "strict", "raw_score": 0},
    }
    artifact = _make_artifact(metadata=legacy_metadata)
    # enforcement_mode must NOT be present (this is the backward-compat case)
    assert "enforcement_mode" not in artifact["metadata"]
    validate(instance=artifact, schema=audit_schema)
