# tests/test_workflow_trace.py
"""Tests for workflow timeline reconstruction."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest

from aigc._internal.workflow_trace import reconstruct_trace
from aigc._internal.cli import main as cli_main


def _cs(artifact):
    """Canonical checksum — must match audit.checksum() and session._checksum()."""
    from aigc._internal.utils import canonical_json_bytes
    return hashlib.sha256(canonical_json_bytes(artifact)).hexdigest()


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


class TestReconstructTrace:
    def test_resolved_step_has_invocation_summary(self):
        trace = reconstruct_trace(WORKFLOW_ARTIFACT, [INV_ARTIFACT])
        assert trace["step_count"] == 1
        step = trace["steps"][0]
        assert step["resolved"] is True
        assert step["sequence"] == 1
        assert step["invocation_summary"]["enforcement_result"] == "PASS"
        assert step["invocation_summary"]["model_provider"] == "openai"

    def test_unresolved_step_when_no_invocation_provided(self):
        trace = reconstruct_trace(WORKFLOW_ARTIFACT, [])
        step = trace["steps"][0]
        assert step["resolved"] is False
        assert step["invocation_summary"] is None
        assert INV_CHECKSUM in trace["unresolved_checksums"]

    def test_top_level_fields(self):
        trace = reconstruct_trace(WORKFLOW_ARTIFACT, [INV_ARTIFACT])
        assert trace["session_id"] == "sess-abc"
        assert trace["status"] == "COMPLETED"
        assert trace["policy_file"] == "governance/policy.yaml"
        assert trace["started_at"] == 1700000000
        assert trace["finalized_at"] == 1700000010
        assert trace["duration_seconds"] == 10
        assert trace["unresolved_checksums"] == []

    def test_empty_steps(self):
        wa = {**WORKFLOW_ARTIFACT, "steps": [], "invocation_audit_checksums": []}
        trace = reconstruct_trace(wa, [])
        assert trace["step_count"] == 0
        assert trace["steps"] == []
        assert trace["unresolved_checksums"] == []

    def test_step_sequence_numbers(self):
        inv2 = {**INV_ARTIFACT, "timestamp": 1700000006}
        cs2 = _cs(inv2)
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "s1", "participant_id": None, "invocation_artifact_checksum": INV_CHECKSUM},
                {"step_id": "s2", "participant_id": "agent-b", "invocation_artifact_checksum": cs2},
            ],
            "invocation_audit_checksums": [INV_CHECKSUM, cs2],
        }
        trace = reconstruct_trace(wa, [INV_ARTIFACT, inv2])
        assert trace["steps"][0]["sequence"] == 1
        assert trace["steps"][1]["sequence"] == 2
        assert trace["step_count"] == 2

    def test_schema_version_present(self):
        trace = reconstruct_trace(WORKFLOW_ARTIFACT, [INV_ARTIFACT])
        assert trace["trace_schema_version"] == "0.9.0"

    def test_step_missing_checksum_field_is_unresolved(self):
        # Step dict has no invocation_artifact_checksum key at all
        wa = {**WORKFLOW_ARTIFACT, "steps": [{"step_id": "s1"}]}
        trace = reconstruct_trace(wa, [INV_ARTIFACT])
        step = trace["steps"][0]
        assert step["resolved"] is False
        assert step["invocation_artifact_checksum"] is None
        # None checksum must NOT appear in unresolved_checksums list
        assert trace["unresolved_checksums"] == []

    def test_unknown_status_passed_through(self):
        wa = {**WORKFLOW_ARTIFACT, "status": "ABORTED"}
        trace = reconstruct_trace(wa, [INV_ARTIFACT])
        assert trace["status"] == "ABORTED"

    def test_duration_none_when_started_at_missing(self):
        wa = {**WORKFLOW_ARTIFACT, "started_at": None}
        trace = reconstruct_trace(wa, [INV_ARTIFACT])
        assert trace["duration_seconds"] is None

    def test_duplicate_invocation_artifact_in_list(self):
        # Same artifact appears twice — deduped in lookup; step still resolves
        trace = reconstruct_trace(WORKFLOW_ARTIFACT, [INV_ARTIFACT, INV_ARTIFACT])
        assert trace["steps"][0]["resolved"] is True
        assert trace["unresolved_checksums"] == []

    def test_stable_output_shape(self):
        trace = reconstruct_trace(WORKFLOW_ARTIFACT, [INV_ARTIFACT])
        required_top = {
            "trace_schema_version", "session_id", "status", "policy_file",
            "started_at", "finalized_at", "duration_seconds", "step_count",
            "steps", "unresolved_checksums", "failure_summary",
        }
        assert required_top <= set(trace.keys())
        step = trace["steps"][0]
        required_step = {
            "sequence", "step_id", "participant_id",
            "invocation_artifact_checksum", "resolved", "invocation_summary",
        }
        assert required_step <= set(step.keys())


class TestWorkflowTraceCLI:
    def _write_jsonl(self, artifacts):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        for a in artifacts:
            f.write(json.dumps(a) + "\n")
        f.close()
        return f.name

    def test_trace_stdout_exits_0(self):
        path = self._write_jsonl([WORKFLOW_ARTIFACT, INV_ARTIFACT])
        try:
            rc = cli_main(["workflow", "trace", "--input", path])
            assert rc == 0
        finally:
            os.unlink(path)

    def test_trace_outputs_valid_json_array(self, capsys):
        path = self._write_jsonl([WORKFLOW_ARTIFACT, INV_ARTIFACT])
        try:
            cli_main(["workflow", "trace", "--input", path])
            out = capsys.readouterr().out
            traces = json.loads(out)
            assert isinstance(traces, list)
            assert len(traces) == 1
            assert traces[0]["session_id"] == "sess-abc"
        finally:
            os.unlink(path)

    def test_trace_file_output(self, tmp_path):
        jsonl_path = self._write_jsonl([WORKFLOW_ARTIFACT, INV_ARTIFACT])
        out_path = str(tmp_path / "trace.json")
        try:
            rc = cli_main(["workflow", "trace", "--input", jsonl_path, "--output", out_path])
            assert rc == 0
            result = json.loads(Path(out_path).read_text())
            assert isinstance(result, list)
            assert result[0]["trace_schema_version"] == "0.9.0"
        finally:
            os.unlink(jsonl_path)

    def test_trace_missing_input_exits_1(self):
        rc = cli_main(["workflow", "trace", "--input", "/nonexistent/file.jsonl"])
        assert rc == 1

    def test_trace_no_workflow_artifacts_exits_1(self):
        path = self._write_jsonl([INV_ARTIFACT])  # no workflow artifact
        try:
            rc = cli_main(["workflow", "trace", "--input", path])
            assert rc == 1
        finally:
            os.unlink(path)

    def test_trace_unresolved_checksums_in_output(self, capsys):
        path = self._write_jsonl([WORKFLOW_ARTIFACT])  # workflow artifact only, no invocation
        try:
            cli_main(["workflow", "trace", "--input", path])
            out = capsys.readouterr().out
            traces = json.loads(out)
            assert traces[0]["unresolved_checksums"] == [INV_CHECKSUM]
        finally:
            os.unlink(path)

    def test_trace_fails_on_malformed_jsonl_line(self, capsys):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write("{not valid json}\n")
        f.write(json.dumps(WORKFLOW_ARTIFACT) + "\n")
        f.write(json.dumps(INV_ARTIFACT) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "trace", "--input", f.name])
            assert rc == 1
            err = capsys.readouterr().err
            assert "malformed JSONL" in err
        finally:
            os.unlink(f.name)

    def test_trace_fails_on_non_dict_jsonl_line(self, capsys):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write("[1, 2, 3]\n")  # valid JSON but not an object
        f.write(json.dumps(WORKFLOW_ARTIFACT) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "trace", "--input", f.name])
            assert rc == 1
            err = capsys.readouterr().err
            assert "malformed JSONL" in err
        finally:
            os.unlink(f.name)

    def test_trace_exits_0_with_unresolved_checksums(self, capsys):
        # Unresolved checksums are advisory — CLI must still exit 0
        path = self._write_jsonl([WORKFLOW_ARTIFACT])
        try:
            rc = cli_main(["workflow", "trace", "--input", path])
            assert rc == 0
        finally:
            os.unlink(path)

    def test_unwritable_output_path_exits_1(self):
        path = self._write_jsonl([WORKFLOW_ARTIFACT, INV_ARTIFACT])
        try:
            rc = cli_main([
                "workflow", "trace",
                "--input", path,
                "--output", "/nonexistent-parent-dir/trace.json",
            ])
            assert rc == 1
        finally:
            os.unlink(path)

    def test_corrupt_steps_in_workflow_artifact_exits_1(self):
        corrupt_wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [123, {"step_id": "s2", "participant_id": "p2", "invocation_artifact_checksum": "b" * 64}],
        }
        path = self._write_jsonl([corrupt_wa, INV_ARTIFACT])
        try:
            rc = cli_main(["workflow", "trace", "--input", path])
            assert rc == 1
        finally:
            os.unlink(path)


class TestChecksumMultiplicity:
    """Regression tests for duplicate-checksum steps losing multiplicity (High finding)."""

    def test_two_steps_same_checksum_single_artifact_first_resolves_second_does_not(self):
        # Two steps reference the same checksum; only one artifact is available.
        # The first step should resolve, the second should be unresolved.
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "s1", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
                {"step_id": "s2", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
            ],
            "invocation_audit_checksums": [INV_CHECKSUM, INV_CHECKSUM],
        }
        trace = reconstruct_trace(wa, [INV_ARTIFACT])
        assert trace["steps"][0]["resolved"] is True
        assert trace["steps"][1]["resolved"] is False
        assert trace["unresolved_checksums"] == [INV_CHECKSUM]

    def test_two_steps_same_checksum_two_artifacts_both_resolve(self):
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": "s1", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
                {"step_id": "s2", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM},
            ],
            "invocation_audit_checksums": [INV_CHECKSUM, INV_CHECKSUM],
        }
        trace = reconstruct_trace(wa, [INV_ARTIFACT, INV_ARTIFACT])
        assert trace["steps"][0]["resolved"] is True
        assert trace["steps"][1]["resolved"] is True
        assert trace["unresolved_checksums"] == []

    def test_unresolved_count_matches_missing_duplicate_occurrences(self):
        # Three steps same checksum, two artifacts — one slot unresolved.
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [
                {"step_id": f"s{i}", "participant_id": "agent", "invocation_artifact_checksum": INV_CHECKSUM}
                for i in range(3)
            ],
            "invocation_audit_checksums": [INV_CHECKSUM] * 3,
        }
        trace = reconstruct_trace(wa, [INV_ARTIFACT, INV_ARTIFACT])
        assert len(trace["unresolved_checksums"]) == 1
        assert trace["unresolved_checksums"] == [INV_CHECKSUM]


class TestMalformedTimestamp:
    """Regression tests for malformed started_at/finalized_at crashing trace (Medium finding)."""

    def test_string_started_at_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "started_at": "1"}
        with pytest.raises(ValueError, match="started_at must be numeric"):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_string_finalized_at_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "finalized_at": "bad"}
        with pytest.raises(ValueError, match="finalized_at must be numeric"):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_list_started_at_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "started_at": []}
        with pytest.raises(ValueError, match="started_at must be numeric"):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_bool_started_at_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "started_at": True}
        with pytest.raises(ValueError, match="started_at must be numeric"):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_bool_finalized_at_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "finalized_at": False}
        with pytest.raises(ValueError, match="finalized_at must be numeric"):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_malformed_started_at_cli_exits_1(self, capsys):
        import tempfile
        import os
        import json
        wa = {**WORKFLOW_ARTIFACT, "started_at": "1"}
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write(json.dumps(wa) + "\n")
        f.close()
        try:
            from aigc._internal.cli import main as cli_main
            rc = cli_main(["workflow", "trace", "--input", f.name])
            assert rc == 1
            err = capsys.readouterr().err
            assert "started_at" in err or "ERROR" in err
        finally:
            os.unlink(f.name)


class TestMalformedStepsContainer:
    """Regression: steps: null must raise ValueError, not TypeError."""

    def test_null_steps_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "steps": None}
        with pytest.raises(ValueError, match="'steps' must be a list"):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_null_steps_cli_exits_1(self, capsys):
        wa = {**WORKFLOW_ARTIFACT, "steps": None}
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write(json.dumps(wa) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "trace", "--input", f.name])
            assert rc == 1
            assert "ERROR" in capsys.readouterr().err
        finally:
            os.unlink(f.name)


class TestMalformedChecksumContainer:
    """Regression: invocation_audit_checksums: null/string must raise ValueError, not TypeError."""

    def test_null_invocation_audit_checksums_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": None}
        with pytest.raises(ValueError, match="'invocation_audit_checksums' must be a list"):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_string_invocation_audit_checksums_raises_value_error(self):
        # A bare string iterates as individual characters — must fail closed.
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": "abc"}
        with pytest.raises(ValueError, match="'invocation_audit_checksums' must be a list"):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_null_invocation_audit_checksums_cli_exits_1(self, capsys):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": None}
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write(json.dumps(wa) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "trace", "--input", f.name])
            assert rc == 1
            assert "ERROR" in capsys.readouterr().err
        finally:
            os.unlink(f.name)

    def test_string_invocation_audit_checksums_cli_exits_1(self, capsys):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": "xyz"}
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write(json.dumps(wa) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "trace", "--input", f.name])
            assert rc == 1
            assert "ERROR" in capsys.readouterr().err
        finally:
            os.unlink(f.name)

    def test_integer_element_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": [1, "abc"]}
        with pytest.raises(ValueError, match=r"invocation_audit_checksums\[0\].*must be a string"):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_nested_list_element_raises_value_error(self):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": [["nested"]]}
        with pytest.raises(ValueError, match=r"invocation_audit_checksums\[0\].*must be a string"):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_non_string_element_cli_exits_1(self, capsys):
        wa = {**WORKFLOW_ARTIFACT, "invocation_audit_checksums": [99]}
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write(json.dumps(wa) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "trace", "--input", f.name])
            assert rc == 1
            assert "ERROR" in capsys.readouterr().err
        finally:
            os.unlink(f.name)

    def test_integer_step_checksum_raises_value_error(self):
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [{"step_id": "s1", "participant_id": None, "invocation_artifact_checksum": 99}],
        }
        with pytest.raises(
            ValueError,
            match=r"steps\[0\]\.invocation_artifact_checksum.*must be a string or null",
        ):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_nested_list_step_checksum_raises_value_error(self):
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [{"step_id": "s1", "participant_id": None, "invocation_artifact_checksum": [99]}],
        }
        with pytest.raises(
            ValueError,
            match=r"steps\[0\]\.invocation_artifact_checksum.*must be a string or null",
        ):
            reconstruct_trace(wa, [INV_ARTIFACT])

    def test_non_string_step_checksum_cli_exits_1(self, capsys):
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [{"step_id": "s1", "participant_id": None, "invocation_artifact_checksum": 99}],
        }
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.write(json.dumps(wa) + "\n")
        f.close()
        try:
            rc = cli_main(["workflow", "trace", "--input", f.name])
            assert rc == 1
            assert "ERROR" in capsys.readouterr().err
        finally:
            os.unlink(f.name)


class TestChecksumCorrelationParity:
    """Regression tests for F-01: session._checksum and audit.checksum must agree."""

    def test_integer_valued_float_resolves_correctly(self):
        """Artifact with risk_score=1.0 must correlate — integer-valued float parity."""
        inv_with_float = {**INV_ARTIFACT, "risk_score": 1.0}
        cs = _cs(inv_with_float)
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [{"step_id": "s1", "participant_id": None, "invocation_artifact_checksum": cs}],
            "invocation_audit_checksums": [cs],
        }
        trace = reconstruct_trace(wa, [inv_with_float])
        assert trace["steps"][0]["resolved"] is True
        assert trace["unresolved_checksums"] == []

    def test_non_ascii_content_resolves_correctly(self):
        """Artifact with non-ASCII text must correlate via UTF-8 canonical bytes."""
        inv_unicode = {**INV_ARTIFACT, "context": {"note": "résumé — 日本語"}}
        cs = _cs(inv_unicode)
        wa = {
            **WORKFLOW_ARTIFACT,
            "steps": [{"step_id": "s1", "participant_id": None, "invocation_artifact_checksum": cs}],
            "invocation_audit_checksums": [cs],
        }
        trace = reconstruct_trace(wa, [inv_unicode])
        assert trace["steps"][0]["resolved"] is True
        assert trace["unresolved_checksums"] == []

    def test_checksum_helpers_agree_on_plain_artifact(self):
        """canonical_json_bytes path and audit.checksum must agree on a plain artifact."""
        from aigc._internal.audit import checksum as audit_checksum
        assert _cs(INV_ARTIFACT) == audit_checksum(INV_ARTIFACT)

    def test_checksum_helpers_agree_on_integer_float(self):
        """canonical_json_bytes path and audit.checksum must agree for risk_score=1.0."""
        from aigc._internal.audit import checksum as audit_checksum
        inv = {**INV_ARTIFACT, "risk_score": 1.0}
        assert _cs(inv) == audit_checksum(inv)
