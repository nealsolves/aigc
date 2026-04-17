"""Tests for the AIGC Policy CLI."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from aigc._internal.cli import main, _lint_policy, _validate_policy


POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden_replays"


class TestLintPolicy:
    """Unit tests for _lint_policy."""

    def test_valid_policy_returns_no_errors(self):
        errors = _lint_policy(POLICIES_DIR / "base_policy.yaml")
        assert errors == []

    def test_invalid_yaml_returns_parse_error(self):
        errors = _lint_policy(GOLDEN_DIR / "invalid_policy.yaml")
        assert len(errors) == 1
        assert "YAML parse error" in errors[0]

    def test_nonexistent_file_returns_error(self):
        errors = _lint_policy(Path("/nonexistent/policy.yaml"))
        assert len(errors) == 1
        assert "Cannot read file" in errors[0]

    def test_non_dict_yaml_returns_error(self):
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False
        ) as f:
            f.write("- just\n- a\n- list\n")
            f.flush()
            try:
                errors = _lint_policy(Path(f.name))
                assert len(errors) == 1
                assert "mapping" in errors[0]
            finally:
                os.unlink(f.name)

    def test_schema_violation_returns_errors(self):
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False
        ) as f:
            # Missing required policy_version
            f.write("roles:\n  - planner\n")
            f.flush()
            try:
                errors = _lint_policy(Path(f.name))
                assert len(errors) > 0
                assert any("policy_version" in e for e in errors)
            finally:
                os.unlink(f.name)


class TestValidatePolicy:
    """Unit tests for _validate_policy."""

    def test_valid_policy_returns_no_errors(self):
        errors = _validate_policy(POLICIES_DIR / "base_policy.yaml")
        assert errors == []

    def test_missing_extends_base_returns_error(self):
        errors = _validate_policy(
            GOLDEN_DIR / "policy_extends_nonexistent.yaml"
        )
        assert len(errors) > 0


class TestCLIMain:
    """Integration tests for the CLI entry point."""

    def test_lint_valid_policy_exits_0(self):
        exit_code = main(["policy", "lint", str(POLICIES_DIR / "base_policy.yaml")])
        assert exit_code == 0

    def test_lint_invalid_policy_exits_1(self):
        exit_code = main(["policy", "lint", str(GOLDEN_DIR / "invalid_policy.yaml")])
        assert exit_code == 1

    def test_lint_nonexistent_file_exits_1(self):
        exit_code = main(["policy", "lint", "/nonexistent/policy.yaml"])
        assert exit_code == 1

    def test_validate_valid_policy_exits_0(self):
        exit_code = main(["policy", "validate", str(POLICIES_DIR / "base_policy.yaml")])
        assert exit_code == 0

    def test_validate_invalid_policy_exits_1(self):
        exit_code = main(["policy", "validate", str(GOLDEN_DIR / "invalid_policy.yaml")])
        assert exit_code == 1

    def test_no_command_exits_1(self):
        exit_code = main([])
        assert exit_code == 1

    def test_multiple_files(self):
        exit_code = main([
            "policy", "lint",
            str(POLICIES_DIR / "base_policy.yaml"),
            str(GOLDEN_DIR / "invalid_policy.yaml"),
        ])
        assert exit_code == 1  # one invalid = overall fail

    def test_cli_importable_from_public_api(self):
        from aigc.cli import main as public_main
        assert callable(public_main)


MINIMAL_VALID_POLICY = 'policy_version: "1.0"\nroles:\n  - ai-assistant\n'


def _make_starter_dir(tmp_path: Path) -> Path:
    d = tmp_path / "starter"
    d.mkdir()
    (d / "policy.yaml").write_text(MINIMAL_VALID_POLICY, encoding="utf-8")
    (d / "workflow_example.py").write_text("import aigc\n\ndef run(): pass\n", encoding="utf-8")
    (d / "README.md").write_text("# Starter\n", encoding="utf-8")
    return d


def _make_workflow_artifact(tmp_path: Path, status: str = "COMPLETED") -> Path:
    checksums = ["a" * 64, "b" * 64]
    artifact = {
        "workflow_schema_version": "1.0",
        "artifact_type": "workflow",
        "session_id": "sess-001",
        "status": status,
        "started_at": 1700000000,
        "finalized_at": 1700000100,
        "steps": [{"step_id": "step-0"}, {"step_id": "step-1"}],
        "invocation_audit_checksums": checksums,
        "failure_summary": None,
        "metadata": {},
    }
    p = tmp_path / "wf.json"
    p.write_text(json.dumps(artifact), encoding="utf-8")
    return p


class TestWorkflowLintCLI:
    """CLI tests for aigc workflow lint."""

    def test_valid_policy_exits_0(self, tmp_path):
        p = tmp_path / "policy.yaml"
        p.write_text(MINIMAL_VALID_POLICY, encoding="utf-8")
        exit_code = main(["workflow", "lint", str(p)])
        assert exit_code == 0

    def test_invalid_policy_exits_1(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("roles: [unclosed", encoding="utf-8")
        exit_code = main(["workflow", "lint", str(p)])
        assert exit_code == 1

    def test_valid_starter_dir_exits_0(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        exit_code = main(["workflow", "lint", str(d)])
        assert exit_code == 0

    def test_invalid_starter_dir_exits_1(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        (d / "README.md").unlink()
        exit_code = main(["workflow", "lint", str(d)])
        assert exit_code == 1

    def test_valid_workflow_artifact_exits_0(self, tmp_path):
        p = _make_workflow_artifact(tmp_path)
        exit_code = main(["workflow", "lint", str(p)])
        assert exit_code == 0

    def test_json_flag_outputs_parseable_json(self, tmp_path, capsys):
        p = tmp_path / "policy.yaml"
        p.write_text(MINIMAL_VALID_POLICY, encoding="utf-8")
        exit_code = main(["workflow", "lint", str(p), "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert isinstance(parsed, list)
        assert parsed[0]["findings"] == []

    def test_multiple_targets_one_fail_exits_1(self, tmp_path):
        good = tmp_path / "good.yaml"
        good.write_text(MINIMAL_VALID_POLICY, encoding="utf-8")
        bad = tmp_path / "bad.yaml"
        bad.write_text("roles: [unclosed", encoding="utf-8")
        exit_code = main(["workflow", "lint", str(good), str(bad)])
        assert exit_code == 1


class TestWorkflowDoctorCLI:
    """CLI tests for aigc workflow doctor."""

    def test_valid_policy_exits_0(self, tmp_path):
        p = tmp_path / "policy.yaml"
        p.write_text(MINIMAL_VALID_POLICY, encoding="utf-8")
        exit_code = main(["workflow", "doctor", str(p)])
        assert exit_code == 0

    def test_expired_policy_exits_1(self, tmp_path):
        content = MINIMAL_VALID_POLICY + "expiration_date: '2000-01-01'\n"
        p = tmp_path / "expired.yaml"
        p.write_text(content, encoding="utf-8")
        exit_code = main(["workflow", "doctor", str(p)])
        assert exit_code == 1

    def test_standard_starter_dir_exits_0_with_advisory(self, tmp_path):
        d = tmp_path / "starter"
        d.mkdir()
        (d / "policy.yaml").write_text(MINIMAL_VALID_POLICY, encoding="utf-8")
        (d / "README.md").write_text("# Starter\n", encoding="utf-8")
        workflow_src = (
            "import aigc\n\n"
            "def _request_human_approval(s): return True\n\n"
            "def run():\n"
            "    g = aigc.AIGC()\n"
            "    with g.open_session(policy_file=None) as s:\n"
            "        s.pause()\n"
            "        s.resume()\n"
            "        s.complete()\n"
        )
        (d / "workflow_example.py").write_text(workflow_src, encoding="utf-8")
        exit_code = main(["workflow", "doctor", str(d)])
        # INFO findings -> exit 0
        assert exit_code == 0

    def test_json_flag_outputs_parseable_json(self, tmp_path, capsys):
        p = tmp_path / "policy.yaml"
        p.write_text(MINIMAL_VALID_POLICY, encoding="utf-8")
        exit_code = main(["workflow", "doctor", str(p), "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert isinstance(parsed, list)

    def test_provenance_fail_artifact_exits_1(self, tmp_path):
        artifact = {
            "audit_schema_version": "1.0",
            "policy_file": "policies/base_policy.yaml",
            "policy_schema_version": "1.0",
            "policy_version": "1.0",
            "model_provider": "anthropic",
            "model_identifier": "claude-sonnet-4-6",
            "role": "ai-assistant",
            "enforcement_result": "FAIL",
            "failures": [
                {"code": "PROVENANCE_MISSING", "message": "source_ids required", "field": None}
            ],
            "failure_gate": "custom_gate_violation",
            "failure_reason": "ProvenanceGate: source_ids are required",
            "input_checksum": "a" * 64,
            "output_checksum": "b" * 64,
            "timestamp": 1700000000,
            "context": {},
            "metadata": {},
            "risk_score": None,
            "signature": None,
            "provenance": None,
            "chain_id": None,
            "chain_index": None,
            "previous_audit_checksum": None,
            "checksum": None,
        }
        p = tmp_path / "audit.json"
        p.write_text(json.dumps(artifact), encoding="utf-8")
        exit_code = main(["workflow", "doctor", str(p), "--kind", "audit_artifact"])
        assert exit_code == 1

    def test_token_misuse_artifact_json_flag(self, tmp_path, capsys):
        artifact = {
            "audit_schema_version": "1.0",
            "policy_file": "policies/base_policy.yaml",
            "policy_schema_version": "1.0",
            "policy_version": "1.0",
            "model_provider": "anthropic",
            "model_identifier": "claude-sonnet-4-6",
            "role": "ai-assistant",
            "enforcement_result": "FAIL",
            "failures": [],
            "failure_gate": "invocation_validation",
            "failure_reason": "SessionPreCallResult cannot be completed via enforce_post_call()",
            "input_checksum": "a" * 64,
            "output_checksum": "b" * 64,
            "timestamp": 1700000000,
            "context": {},
            "metadata": {},
            "risk_score": None,
            "signature": None,
            "provenance": None,
            "chain_id": None,
            "chain_index": None,
            "previous_audit_checksum": None,
            "checksum": None,
        }
        p = tmp_path / "token.json"
        p.write_text(json.dumps(artifact), encoding="utf-8")
        exit_code = main(
            ["workflow", "doctor", str(p), "--kind", "audit_artifact", "--json"]
        )
        assert exit_code == 1
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        codes = [f["code"] for f in parsed]
        assert "WORKFLOW_SESSION_TOKEN_INVALID" in codes
