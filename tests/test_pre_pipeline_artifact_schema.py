"""
Tests that pre-pipeline FAIL artifacts are schema-valid.

Pre-pipeline failures (policy load errors, invocation validation errors) are
handled by ``_generate_pre_pipeline_fail_artifact()`` before the enforcement
pipeline starts.  These artifacts must satisfy the audit artifact JSON schema
just like any in-pipeline artifact.

Covers:
- Policy load failure produces a schema-valid artifact
- Invocation validation failure produces a schema-valid artifact
- ``policy_version`` is the string ``"unknown"`` (not None/null)
- ``policy_file`` defaults to ``"unknown"`` when invocation lacks it
- ``failure_gate`` is a valid enum value from the schema
- ``enforcement_result`` is ``"FAIL"``
- ``metadata.pre_pipeline_failure`` is ``True``
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import validate, ValidationError

from aigc._internal.enforcement import enforce_invocation
from aigc._internal.errors import (
    AIGCError,
    InvocationValidationError,
    PolicyLoadError,
)

# ── Schema fixture ────────────────────────────────────────────────

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "audit_artifact.schema.json"


@pytest.fixture(scope="module")
def audit_schema() -> dict:
    """Load the audit artifact JSON schema once per module."""
    return json.loads(SCHEMA_PATH.read_text())


# ── Helper invocations ────────────────────────────────────────────

def _policy_load_failure_invocation() -> dict:
    """Invocation referencing a non-existent policy file."""
    return {
        "policy_file": "nonexistent/policy.yaml",
        "model_provider": "test",
        "model_identifier": "test-model",
        "role": "tester",
        "input": {"prompt": "hello"},
        "output": {"result": "world"},
        "context": {},
    }


def _missing_fields_invocation() -> dict:
    """Invocation missing several required fields."""
    return {
        "model_provider": "test",
        "input": {"prompt": "hello"},
    }


def _missing_policy_file_invocation() -> dict:
    """Invocation missing only the policy_file field."""
    return {
        "model_provider": "test",
        "model_identifier": "test-model",
        "role": "tester",
        "input": {"prompt": "hello"},
        "output": {"result": "world"},
        "context": {},
    }


# ── Tests ─────────────────────────────────────────────────────────

class TestPolicyLoadFailureArtifact:
    """Pre-pipeline FAIL artifact from a policy-load error."""

    def test_artifact_is_schema_valid(self, audit_schema: dict) -> None:
        """A missing-policy failure must produce a schema-valid artifact."""
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_policy_load_failure_invocation())

        artifact = exc_info.value.audit_artifact
        assert artifact is not None

        # jsonschema.validate raises ValidationError on mismatch
        validate(instance=artifact, schema=audit_schema)

    def test_enforcement_result_is_fail(self) -> None:
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_policy_load_failure_invocation())

        assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"

    def test_policy_version_is_unknown_string(self) -> None:
        """policy_version must be the string 'unknown', not None."""
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_policy_load_failure_invocation())

        artifact = exc_info.value.audit_artifact
        assert artifact["policy_version"] == "unknown"
        assert artifact["policy_version"] is not None

    def test_failure_gate_is_valid_enum(self, audit_schema: dict) -> None:
        """failure_gate must be one of the enum values in the schema."""
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_policy_load_failure_invocation())

        artifact = exc_info.value.audit_artifact
        allowed = audit_schema["properties"]["failure_gate"]["enum"]
        assert artifact["failure_gate"] in allowed

    def test_pre_pipeline_failure_metadata(self) -> None:
        """metadata.pre_pipeline_failure must be True."""
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_policy_load_failure_invocation())

        metadata = exc_info.value.audit_artifact["metadata"]
        assert metadata["pre_pipeline_failure"] is True


class TestInvocationValidationFailureArtifact:
    """Pre-pipeline FAIL artifact from invocation validation."""

    def test_artifact_is_schema_valid(self, audit_schema: dict) -> None:
        """Missing required invocation fields must still yield a valid artifact."""
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_missing_fields_invocation())

        artifact = exc_info.value.audit_artifact
        assert artifact is not None

        validate(instance=artifact, schema=audit_schema)

    def test_enforcement_result_is_fail(self) -> None:
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_missing_fields_invocation())

        assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"

    def test_policy_version_is_unknown_string(self) -> None:
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_missing_fields_invocation())

        artifact = exc_info.value.audit_artifact
        assert artifact["policy_version"] == "unknown"
        assert artifact["policy_version"] is not None

    def test_failure_gate_is_valid_enum(self, audit_schema: dict) -> None:
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_missing_fields_invocation())

        artifact = exc_info.value.audit_artifact
        allowed = audit_schema["properties"]["failure_gate"]["enum"]
        assert artifact["failure_gate"] in allowed

    def test_pre_pipeline_failure_metadata(self) -> None:
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_missing_fields_invocation())

        metadata = exc_info.value.audit_artifact["metadata"]
        assert metadata["pre_pipeline_failure"] is True


class TestDeterministicPlaceholders:
    """Placeholder defaults for missing / invalid invocation fields."""

    def test_policy_file_defaults_to_unknown(self, audit_schema: dict) -> None:
        """When invocation has no policy_file, artifact uses 'unknown'."""
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_missing_policy_file_invocation())

        artifact = exc_info.value.audit_artifact
        assert artifact["policy_file"] == "unknown"
        # Still schema-valid
        validate(instance=artifact, schema=audit_schema)

    def test_missing_fields_produce_unknown_placeholders(self) -> None:
        """All string fields default to 'unknown' when absent."""
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_missing_fields_invocation())

        artifact = exc_info.value.audit_artifact
        # Fields that were absent in the invocation get safe defaults
        assert isinstance(artifact["policy_file"], str)
        assert len(artifact["policy_file"]) >= 1
        assert isinstance(artifact["model_identifier"], str)
        assert len(artifact["model_identifier"]) >= 1
        assert isinstance(artifact["role"], str)
        assert len(artifact["role"]) >= 1

    def test_gates_evaluated_empty_on_pre_pipeline(self) -> None:
        """No gates should have been evaluated before the pipeline starts."""
        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(_policy_load_failure_invocation())

        metadata = exc_info.value.audit_artifact["metadata"]
        assert metadata["gates_evaluated"] == []


class TestPrePipelineProvenancePreservation:
    """Provenance must survive pre-pipeline failures even when context contains
    non-JSON-serializable entries alongside the provenance mapping."""

    def test_provenance_preserved_when_context_has_non_serializable_sibling(self) -> None:
        """A callback object alongside valid provenance must not cause provenance loss."""
        invocation = {
            "policy_file": "nonexistent/policy.yaml",
            "model_provider": "test",
            "model_identifier": "test-model",
            "role": "tester",
            "input": {"prompt": "hello"},
            "output": {"result": "world"},
            "context": {
                "provenance": {
                    "source_ids": ["audit-abc123"],
                    "derived_from_audit_checksums": ["a" * 64],
                },
                # A non-JSON-serializable sibling — triggers _safe_dict() collapse
                "callback": lambda: None,
            },
        }

        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact["provenance"] is not None, (
            "Provenance must be preserved even when context has non-serializable siblings"
        )
        assert artifact["provenance"]["source_ids"] == ["audit-abc123"]

    def test_provenance_absent_when_context_has_no_provenance(self) -> None:
        """Baseline: context with only non-serializable entries → provenance stays None."""
        invocation = {
            "policy_file": "nonexistent/policy.yaml",
            "model_provider": "test",
            "model_identifier": "test-model",
            "role": "tester",
            "input": {"prompt": "hello"},
            "output": {"result": "world"},
            "context": {
                "callback": lambda: None,
            },
        }

        with pytest.raises(AIGCError) as exc_info:
            enforce_invocation(invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact["provenance"] is None
