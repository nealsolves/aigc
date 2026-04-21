# tests/test_workflow_export.py
"""Tests for workflow export (operator and audit modes)."""
import json
import os
import tempfile
from pathlib import Path

import pytest

from aigc.audit import checksum
from aigc.cli import main as cli_main
from aigc.workflow_export import export_workflow


def _cs(artifact):
    """Canonical checksum — must match audit.checksum() and session._checksum()."""
    return checksum(artifact)


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

    def test_unknown_status_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "status": "ABORTED"}
        with pytest.raises(ValueError, match="unsupported status"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

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

    def test_string_started_at_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "started_at": "2024-01-01T00:00:00Z"}
        with pytest.raises(ValueError, match="started_at must be numeric"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_bool_started_at_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "started_at": True}
        with pytest.raises(ValueError, match="started_at must be numeric"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_string_finalized_at_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "finalized_at": "done"}
        with pytest.raises(ValueError, match="finalized_at must be numeric"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_bool_finalized_at_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "finalized_at": False}
        with pytest.raises(ValueError, match="finalized_at must be numeric"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_null_timestamps_are_allowed(self):
        wa = {**WORKFLOW_ARTIFACT, "started_at": None, "finalized_at": None}
        result = export_workflow([wa], [INV_ARTIFACT], "audit")
        session = result["sessions"][0]
        assert session["started_at"] is None
        assert session["finalized_at"] is None

    def test_operator_mode_rejects_string_started_at(self):
        wa = {**WORKFLOW_ARTIFACT, "started_at": "bad"}
        with pytest.raises(ValueError, match="started_at must be numeric"):
            export_workflow([wa], [INV_ARTIFACT], "operator")

    def test_timestamp_error_includes_artifact_index(self):
        wa_good = {**WORKFLOW_ARTIFACT, "session_id": "sess-good"}
        wa_bad = {**WORKFLOW_ARTIFACT, "session_id": "sess-bad", "started_at": "oops"}
        with pytest.raises(ValueError, match="index 1"):
            export_workflow([wa_good, wa_bad], [INV_ARTIFACT], "audit")


class TestWorkflowExportCLI:
    def _write_jsonl(self, artifacts):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        for a in artifacts:
            f.write(json.dumps(a) + "\n")
        f.close()
        return f.name

    def test_operator_mode_exits_0(self):
        path = self._write_jsonl([WORKFLOW_ARTIFACT, INV_ARTIFACT])
        try:
            rc = cli_main(["workflow", "export", "--input", path, "--mode", "operator"])
            assert rc == 0
        finally:
            os.unlink(path)

    def test_audit_mode_exits_0(self):
        path = self._write_jsonl([WORKFLOW_ARTIFACT, INV_ARTIFACT])
        try:
            rc = cli_main(["workflow", "export", "--input", path, "--mode", "audit"])
            assert rc == 0
        finally:
            os.unlink(path)

    def test_operator_output_valid_json(self, capsys):
        path = self._write_jsonl([WORKFLOW_ARTIFACT, INV_ARTIFACT])
        try:
            cli_main(["workflow", "export", "--input", path, "--mode", "operator"])
            out = capsys.readouterr().out
            result = json.loads(out)
            assert result["export_mode"] == "operator"
            assert result["export_schema_version"] == "0.9.0"
        finally:
            os.unlink(path)

    def test_audit_output_valid_json(self, capsys):
        path = self._write_jsonl([WORKFLOW_ARTIFACT, INV_ARTIFACT])
        try:
            cli_main(["workflow", "export", "--input", path, "--mode", "audit"])
            out = capsys.readouterr().out
            result = json.loads(out)
            assert result["export_mode"] == "audit"
            assert "compliance_summary" in result
        finally:
            os.unlink(path)

    def test_file_output_written(self, tmp_path):
        jsonl_path = self._write_jsonl([WORKFLOW_ARTIFACT, INV_ARTIFACT])
        out_path = str(tmp_path / "export.json")
        try:
            rc = cli_main(
                ["workflow", "export", "--input", jsonl_path, "--mode", "audit", "--output", out_path]
            )
            assert rc == 0
            data = json.loads(Path(out_path).read_text())
            assert data["export_mode"] == "audit"
        finally:
            os.unlink(jsonl_path)

    def test_missing_input_exits_1(self):
        rc = cli_main(["workflow", "export", "--input", "/no/file.jsonl", "--mode", "operator"])
        assert rc == 1

    def test_no_workflow_artifacts_exits_1(self):
        path = self._write_jsonl([INV_ARTIFACT])  # no workflow artifact
        try:
            rc = cli_main(["workflow", "export", "--input", path, "--mode", "operator"])
            assert rc == 1
        finally:
            os.unlink(path)

    def test_unresolved_checksums_in_operator_export(self, capsys):
        path = self._write_jsonl([WORKFLOW_ARTIFACT])  # workflow artifact only
        try:
            cli_main(["workflow", "export", "--input", path, "--mode", "operator"])
            out = capsys.readouterr().out
            result = json.loads(out)
            assert result["integrity"]["unresolved_count"] == 1
        finally:
            os.unlink(path)

    def test_export_exits_0_with_unresolved_checksums(self):
        # Unresolved checksums are advisory — CLI must still exit 0
        path = self._write_jsonl([WORKFLOW_ARTIFACT])
        try:
            rc = cli_main(["workflow", "export", "--input", path, "--mode", "audit"])
            assert rc == 0
        finally:
            os.unlink(path)

    def test_unwritable_output_path_exits_1(self):
        path = self._write_jsonl([WORKFLOW_ARTIFACT, INV_ARTIFACT])
        try:
            rc = cli_main([
                "workflow", "export",
                "--input", path,
                "--mode", "operator",
                "--output", "/nonexistent-parent-dir/export.json",
            ])
            assert rc == 1
        finally:
            os.unlink(path)

    def test_export_fails_on_malformed_jsonl_line(self, capsys):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write("{not valid json}\n")
        f.write(json.dumps(WORKFLOW_ARTIFACT) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "export", "--input", f.name, "--mode", "operator"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "malformed JSONL" in err
        finally:
            os.unlink(f.name)

    def test_export_fails_on_non_dict_jsonl_line(self, capsys):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write("[1, 2, 3]\n")  # valid JSON but not an object
        f.write(json.dumps(WORKFLOW_ARTIFACT) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "export", "--input", f.name, "--mode", "audit"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "malformed JSONL" in err
        finally:
            os.unlink(f.name)

    def test_corrupt_steps_in_workflow_artifact_exits_1(self):
        corrupt_wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [123, {"step_id": "s2", "participant_id": "p2", "invocation_artifact_checksum": "b" * 64}],
        }
        path = self._write_jsonl([corrupt_wa, INV_ARTIFACT])
        try:
            rc = cli_main(["workflow", "export", "--input", path, "--mode", "audit"])
            assert rc == 1
        finally:
            os.unlink(path)


class TestExportIntegrityStepReferenceParity:
    """Regression tests for F-01: export unresolved set must include step references
    absent from invocation_audit_checksums, keeping trace/export accounting aligned."""

    def test_step_ref_absent_from_summary_list_is_unresolved(self):
        # steps[0] references a checksum that was never added to invocation_audit_checksums.
        # Export must still report it unresolved (same as trace would).
        orphan_cs = "f" * 64
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "step-1", "participant_id": "agent", "invocation_artifact_checksum": orphan_cs}
            ],
            "invocation_audit_checksums": [],  # summary list intentionally empty
        }
        result = export_workflow([wa], [], "operator")
        assert result["integrity"]["unresolved_count"] == 1
        assert orphan_cs in result["integrity"]["unresolved_invocation_checksums"]

    def test_step_ref_absent_from_summary_list_is_unresolved_audit_mode(self):
        orphan_cs = "e" * 64
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "step-1", "participant_id": "agent", "invocation_artifact_checksum": orphan_cs}
            ],
            "invocation_audit_checksums": [],
        }
        result = export_workflow([wa], [], "audit")
        assert result["integrity"]["unresolved_count"] == 1
        assert orphan_cs in result["integrity"]["unresolved_invocation_checksums"]

    def test_step_ref_provided_as_artifact_resolves(self):
        # When the artifact is supplied, a step ref absent from invocation_audit_checksums
        # is still resolved because export now checks step references directly.
        orphan_inv = {**INV_ARTIFACT, "timestamp": 9999999}
        orphan_cs = _cs(orphan_inv)
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "step-1", "participant_id": "agent", "invocation_artifact_checksum": orphan_cs}
            ],
            "invocation_audit_checksums": [],
        }
        result = export_workflow([wa], [orphan_inv], "operator")
        assert result["integrity"]["unresolved_count"] == 0
        assert result["integrity"]["unresolved_invocation_checksums"] == []

    def test_summary_list_ref_absent_from_steps_is_still_unresolved(self):
        # A checksum in invocation_audit_checksums but with no matching artifact
        # must remain unresolved regardless of step presence.
        extra_cs = "d" * 64
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [],
            "invocation_audit_checksums": [extra_cs],
        }
        result = export_workflow([wa], [], "operator")
        assert result["integrity"]["unresolved_count"] == 1
        assert extra_cs in result["integrity"]["unresolved_invocation_checksums"]


class TestChecksumMultiplicityExport:
    """Regression tests for duplicate-checksum steps losing multiplicity (High finding)."""

    def test_two_steps_same_checksum_single_artifact_reports_one_unresolved(self):
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "s1", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
                {"step_id": "s2", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
            ],
            "invocation_audit_checksums": [INV_CHECKSUM, INV_CHECKSUM],
        }
        result = export_workflow([wa], [INV_ARTIFACT], "operator")
        assert result["integrity"]["unresolved_count"] == 1
        assert INV_CHECKSUM in result["integrity"]["unresolved_invocation_checksums"]

    def test_two_steps_same_checksum_two_artifacts_fully_resolved(self):
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "s1", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
                {"step_id": "s2", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
            ],
            "invocation_audit_checksums": [INV_CHECKSUM, INV_CHECKSUM],
        }
        result = export_workflow([wa], [INV_ARTIFACT, INV_ARTIFACT], "operator")
        assert result["integrity"]["unresolved_count"] == 0

    def test_total_invocation_artifacts_counts_duplicates(self):
        # Supplying two identical artifacts (same checksum) must count as 2.
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "s1", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
                {"step_id": "s2", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
            ],
            "invocation_audit_checksums": [INV_CHECKSUM, INV_CHECKSUM],
        }
        result = export_workflow([wa], [INV_ARTIFACT, INV_ARTIFACT], "operator")
        assert result["integrity"]["total_invocation_artifacts"] == 2

    def test_cross_session_same_checksum_requires_two_artifacts(self):
        # Two sessions each reference the same checksum once. The sink writes one
        # line per emitted artifact, so two artifacts are expected — one per session.
        # One artifact present → one unresolved occurrence.
        wa2 = {**WORKFLOW_ARTIFACT, "session_id": "sess-xyz"}
        result = export_workflow([WORKFLOW_ARTIFACT, wa2], [INV_ARTIFACT], "operator")
        assert result["integrity"]["unresolved_count"] == 1

    def test_cross_session_same_checksum_two_artifacts_fully_resolved(self):
        # Two sessions, same checksum, two artifacts → fully resolved.
        wa2 = {**WORKFLOW_ARTIFACT, "session_id": "sess-xyz"}
        result = export_workflow([WORKFLOW_ARTIFACT, wa2], [INV_ARTIFACT, INV_ARTIFACT], "operator")
        assert result["integrity"]["unresolved_count"] == 0

    def test_two_steps_same_checksum_single_artifact_operator_second_step_null(self):
        # First step consumes the artifact slot; second step invocation_artifact must be None.
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "s1", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
                {"step_id": "s2", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
            ],
            "invocation_audit_checksums": [INV_CHECKSUM, INV_CHECKSUM],
        }
        result = export_workflow([wa], [INV_ARTIFACT], "operator")
        steps = result["sessions"][0]["steps"]
        assert steps[0]["invocation_artifact"] is not None
        assert steps[1]["invocation_artifact"] is None

    def test_two_steps_same_checksum_single_artifact_audit_second_step_null_enforcement(self):
        # First step gets enforcement_result; second must be None, not PASS.
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "s1", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
                {"step_id": "s2", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
            ],
            "invocation_audit_checksums": [INV_CHECKSUM, INV_CHECKSUM],
        }
        result = export_workflow([wa], [INV_ARTIFACT], "audit")
        steps = result["sessions"][0]["steps"]
        assert steps[0]["enforcement_result"] == INV_ARTIFACT.get("enforcement_result")
        assert steps[1]["enforcement_result"] is None

    def test_duplicate_checksum_in_audit_mode_reports_unresolved(self):
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "s1", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
                {"step_id": "s2", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
            ],
            "invocation_audit_checksums": [INV_CHECKSUM, INV_CHECKSUM],
        }
        result = export_workflow([wa], [INV_ARTIFACT], "audit")
        assert result["integrity"]["unresolved_count"] == 1


class TestMalformedStatusExport:
    """Regression tests for malformed status crashing export (Medium finding)."""

    def test_list_status_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "status": []}
        with pytest.raises(ValueError, match="status must be a string"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_integer_status_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "status": 0}
        with pytest.raises(ValueError, match="status must be a string"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_malformed_status_cli_exits_1(self, capsys):
        import tempfile
        import os
        import json
        wa = {**WORKFLOW_ARTIFACT, "status": []}
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write(json.dumps(wa) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "export", "--input", f.name, "--mode", "audit"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "ERROR" in err
        finally:
            os.unlink(f.name)

    def test_operator_mode_with_list_status_raises_value_error(self):
        # Status validation happens before mode dispatch — operator mode rejects it too.
        wa = {**WORKFLOW_ARTIFACT, "status": []}
        with pytest.raises(ValueError, match="status must be a string"):
            export_workflow([wa], [INV_ARTIFACT], "operator")

    def test_malformed_status_operator_cli_exits_1(self, capsys):
        import tempfile
        import os
        import json
        wa = {**WORKFLOW_ARTIFACT, "status": []}
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write(json.dumps(wa) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "export", "--input", f.name, "--mode", "operator"])
            assert rc == 1
            err = capsys.readouterr().err
            assert "ERROR" in err
        finally:
            os.unlink(f.name)


class TestMalformedContainersExport:
    """Regression: steps: null and invocation_audit_checksums: null/string must raise ValueError."""

    def _write_jsonl(self, artifacts):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        for a in artifacts:
            f.write(json.dumps(a) + "\n")
        f.close()
        return f.name

    def test_null_steps_raises_value_error_audit(self):
        wa = {**WORKFLOW_ARTIFACT, "steps": None}
        with pytest.raises(ValueError, match="'steps' must be a list"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_null_steps_raises_value_error_operator(self):
        wa = {**WORKFLOW_ARTIFACT, "steps": None}
        with pytest.raises(ValueError, match="'steps' must be a list"):
            export_workflow([wa], [INV_ARTIFACT], "operator")

    def test_null_steps_cli_exits_1(self, capsys):
        wa = {**WORKFLOW_ARTIFACT, "steps": None}
        path = self._write_jsonl([wa])
        try:
            rc = cli_main(["workflow", "export", "--input", path, "--mode", "audit"])
            assert rc == 1
            assert "ERROR" in capsys.readouterr().err
        finally:
            os.unlink(path)

    def test_null_invocation_audit_checksums_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": None}
        with pytest.raises(ValueError, match="'invocation_audit_checksums' must be a list"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_string_invocation_audit_checksums_raises_value_error(self):
        # A bare string iterates as individual characters — must fail closed.
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": "abc"}
        with pytest.raises(ValueError, match="'invocation_audit_checksums' must be a list"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_null_invocation_audit_checksums_cli_exits_1(self, capsys):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": None}
        path = self._write_jsonl([wa])
        try:
            rc = cli_main(["workflow", "export", "--input", path, "--mode", "operator"])
            assert rc == 1
            assert "ERROR" in capsys.readouterr().err
        finally:
            os.unlink(path)

    def test_string_invocation_audit_checksums_cli_exits_1(self, capsys):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": "xyz"}
        path = self._write_jsonl([wa])
        try:
            rc = cli_main(["workflow", "export", "--input", path, "--mode", "operator"])
            assert rc == 1
            assert "ERROR" in capsys.readouterr().err
        finally:
            os.unlink(path)

    def test_integer_element_in_iac_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": [1, "abc"]}
        with pytest.raises(ValueError, match=r"invocation_audit_checksums\[0\].*must be a string"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_nested_list_element_in_iac_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": [["nested"]]}
        with pytest.raises(ValueError, match=r"invocation_audit_checksums\[0\].*must be a string"):
            export_workflow([wa], [INV_ARTIFACT], "operator")

    def test_non_string_iac_element_cli_exits_1(self, capsys):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": [99]}
        path = self._write_jsonl([wa])
        try:
            rc = cli_main(["workflow", "export", "--input", path, "--mode", "audit"])
            assert rc == 1
            assert "ERROR" in capsys.readouterr().err
        finally:
            os.unlink(path)

    def test_integer_step_checksum_raises_value_error(self):
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [{"step_id": "s1", "invocation_artifact_checksum": 42}],
        }
        with pytest.raises(ValueError, match=r"steps\[0\]\.invocation_artifact_checksum.*must be a string"):
            export_workflow([wa], [INV_ARTIFACT], "audit")

    def test_non_string_step_checksum_cli_exits_1(self, capsys):
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [{"step_id": "s1", "invocation_artifact_checksum": 7}],
        }
        path = self._write_jsonl([wa])
        try:
            rc = cli_main(["workflow", "export", "--input", path, "--mode", "operator"])
            assert rc == 1
            assert "ERROR" in capsys.readouterr().err
        finally:
            os.unlink(path)


class TestChecksumCorrelationParityExport:
    """Regression tests for F-01: integer-valued float checksums must resolve in export."""

    def test_integer_valued_float_resolves_in_operator_export(self):
        inv_with_float = {**INV_ARTIFACT, "risk_score": 1.0}
        cs = _cs(inv_with_float)
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [{"step_id": "s1", "participant_id": None, "invocation_artifact_checksum": cs}],
            "invocation_audit_checksums": [cs],
        }
        result = export_workflow([wa], [inv_with_float], "operator")
        assert result["integrity"]["unresolved_count"] == 0
        assert result["integrity"]["unresolved_invocation_checksums"] == []

    def test_integer_valued_float_resolves_in_audit_export(self):
        inv_with_float = {**INV_ARTIFACT, "risk_score": 1.0}
        cs = _cs(inv_with_float)
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [{"step_id": "s1", "participant_id": None, "invocation_artifact_checksum": cs}],
            "invocation_audit_checksums": [cs],
        }
        result = export_workflow([wa], [inv_with_float], "audit")
        assert result["integrity"]["unresolved_count"] == 0
        assert result["sessions"][0]["steps"][0]["enforcement_result"] == "PASS"
