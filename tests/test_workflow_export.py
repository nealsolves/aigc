# tests/test_workflow_export.py
"""Tests for workflow export (operator and audit modes)."""
import hashlib
import json

import pytest

from aigc._internal.workflow_export import export_workflow


def _cs(artifact):
    return hashlib.sha256(
        json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


INV_ARTIFACT = {
    "audit_schema_version": "1.4",
    "policy_file": "governance/policy.yaml",
    "policy_version": "1.0",
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "ai-assistant",
    "enforcement_result": "PASS",
    "failures": [],
    "failure_gate": None,
    "failure_reason": None,
    "input_checksum": "a" * 64,
    "output_checksum": "b" * 64,
    "context": {},
    "timestamp": 1700000005,
    "metadata": {},
    "risk_score": None,
    "signature": None,
    "provenance": None,
}

INV_CHECKSUM = _cs(INV_ARTIFACT)

WORKFLOW_ARTIFACT = {
    "workflow_schema_version": "0.9.0",
    "artifact_type": "workflow",
    "session_id": "sess-abc",
    "policy_file": "governance/policy.yaml",
    "status": "COMPLETED",
    "started_at": 1700000000,
    "finalized_at": 1700000010,
    "steps": [
        {
            "step_id": "step-1",
            "participant_id": "review-agent",
            "invocation_artifact_checksum": INV_CHECKSUM,
        }
    ],
    "invocation_audit_checksums": [INV_CHECKSUM],
    "failure_summary": None,
    "approval_checkpoints": [],
    "validator_hook_evidence": [],
    "metadata": {},
}


class TestOperatorExport:
    def test_schema_fields(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [INV_ARTIFACT], "operator")
        assert result["export_schema_version"] == "0.9.0"
        assert result["export_mode"] == "operator"
        assert "generated_at" in result

    def test_sessions_contains_enriched_steps(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [INV_ARTIFACT], "operator")
        assert len(result["sessions"]) == 1
        step = result["sessions"][0]["steps"][0]
        assert step["invocation_artifact"] == INV_ARTIFACT

    def test_integrity_all_resolved(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [INV_ARTIFACT], "operator")
        integrity = result["integrity"]
        assert integrity["total_workflow_artifacts"] == 1
        assert integrity["total_invocation_artifacts"] == 1
        assert integrity["unresolved_count"] == 0
        assert integrity["unresolved_invocation_checksums"] == []

    def test_integrity_surfaces_unresolved_checksums(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [], "operator")
        integrity = result["integrity"]
        assert integrity["unresolved_count"] == 1
        assert INV_CHECKSUM in integrity["unresolved_invocation_checksums"]

    def test_verification_guidance_present(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [INV_ARTIFACT], "operator")
        assert "verification_guidance" in result["integrity"]
        assert len(result["integrity"]["verification_guidance"]) > 0

    def test_multi_session_partial_evidence(self):
        inv2 = {**INV_ARTIFACT, "timestamp": 1700000020}
        cs2 = _cs(inv2)
        wa2 = {
            **WORKFLOW_ARTIFACT,
            "session_id": "sess-xyz",
            "steps": [{"step_id": "s1", "participant_id": None, "invocation_artifact_checksum": cs2}],
            "invocation_audit_checksums": [cs2],
        }
        result = export_workflow([WORKFLOW_ARTIFACT, wa2], [INV_ARTIFACT], "operator")
        assert len(result["sessions"]) == 2
        assert result["integrity"]["unresolved_count"] == 1
        assert cs2 in result["integrity"]["unresolved_invocation_checksums"]

    def test_stable_operator_output_shape(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [INV_ARTIFACT], "operator")
        required = {"export_schema_version", "export_mode", "generated_at", "sessions", "integrity"}
        assert required <= set(result.keys())
        integrity_keys = {
            "total_workflow_artifacts", "total_invocation_artifacts",
            "unresolved_invocation_checksums", "unresolved_count", "verification_guidance",
        }
        assert integrity_keys <= set(result["integrity"].keys())


class TestAuditExport:
    def test_schema_fields(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [INV_ARTIFACT], "audit")
        assert result["export_schema_version"] == "0.9.0"
        assert result["export_mode"] == "audit"
        assert "generated_at" in result

    def test_compliance_summary(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [INV_ARTIFACT], "audit")
        cs = result["compliance_summary"]
        assert cs["total_sessions"] == 1
        assert cs["COMPLETED"] == 1
        assert cs["FAILED"] == 0

    def test_step_summary_has_enforcement_result(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [INV_ARTIFACT], "audit")
        step = result["sessions"][0]["steps"][0]
        assert step["enforcement_result"] == "PASS"
        assert "invocation_artifact" not in step  # audit mode omits full artifact

    def test_unresolved_checksums_surfaced(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [], "audit")
        assert result["integrity"]["unresolved_count"] == 1

    def test_verification_guidance_present(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [INV_ARTIFACT], "audit")
        assert "verification_guidance" in result["integrity"]
        assert len(result["integrity"]["verification_guidance"]) > 0

    def test_unknown_status_passed_through_without_crash(self):
        wa = {**WORKFLOW_ARTIFACT, "status": "ABORTED"}
        result = export_workflow([wa], [INV_ARTIFACT], "audit")
        assert result["compliance_summary"]["total_sessions"] == 1
        assert result["sessions"][0]["status"] == "ABORTED"

    def test_stable_audit_output_shape(self):
        result = export_workflow([WORKFLOW_ARTIFACT], [INV_ARTIFACT], "audit")
        required = {
            "export_schema_version", "export_mode", "generated_at",
            "sessions", "compliance_summary", "integrity",
        }
        assert required <= set(result.keys())
        cs_keys = {"total_sessions", "COMPLETED", "FAILED", "CANCELED", "INCOMPLETE"}
        assert cs_keys <= set(result["compliance_summary"].keys())
        step = result["sessions"][0]["steps"][0]
        step_keys = {"step_id", "participant_id", "invocation_artifact_checksum", "enforcement_result"}
        assert step_keys <= set(step.keys())


class TestExportValidation:
    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown export mode"):
            export_workflow([WORKFLOW_ARTIFACT], [], "invalid")

    def test_empty_workflow_artifacts(self):
        result = export_workflow([], [], "operator")
        assert result["sessions"] == []
        assert result["integrity"]["total_workflow_artifacts"] == 0
