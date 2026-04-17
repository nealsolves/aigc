"""Tests for aigc._internal.workflow_lint."""

from __future__ import annotations

import json
from pathlib import Path

from aigc._internal.workflow_lint import (
    lint_policy,
    lint_starter_dir,
    lint_workflow_artifact,
    lint_target,
    detect_target_kind,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_VALID_POLICY = """\
policy_version: "1.0"
roles:
  - ai-assistant
"""


def _write(tmp_path: Path, filename: str, content: str) -> str:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return str(p)


def _make_valid_workflow_artifact(steps: int = 2, status: str = "COMPLETED") -> dict:
    checksums = ["a" * 64 for _ in range(steps)]
    return {
        "workflow_schema_version": "1.0",
        "artifact_type": "workflow",
        "session_id": "sess-001",
        "status": status,
        "started_at": 1700000000,
        "finalized_at": 1700000100,
        "steps": [{"step_id": f"step-{i}"} for i in range(steps)],
        "invocation_audit_checksums": checksums,
        "failure_summary": None,
        "metadata": {},
    }


def _make_starter_dir(tmp_path: Path, *, internal_import: bool = False) -> Path:
    """Create a minimal valid starter directory."""
    d = tmp_path / "starter"
    d.mkdir()
    (d / "policy.yaml").write_text(MINIMAL_VALID_POLICY, encoding="utf-8")
    workflow_src = "import aigc\n\ndef run(): pass\n"
    if internal_import:
        workflow_src = "from aigc._internal import errors\n\ndef run(): pass\n"
    (d / "workflow_example.py").write_text(workflow_src, encoding="utf-8")
    (d / "README.md").write_text("# Starter\n", encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# detect_target_kind
# ---------------------------------------------------------------------------

class TestDetectTargetKind:
    def test_yaml_file_is_policy(self, tmp_path):
        p = tmp_path / "policy.yaml"
        p.write_text(MINIMAL_VALID_POLICY)
        assert detect_target_kind(str(p)) == "policy"

    def test_yml_extension_is_policy(self, tmp_path):
        p = tmp_path / "thing.yml"
        p.write_text(MINIMAL_VALID_POLICY)
        assert detect_target_kind(str(p)) == "policy"

    def test_starter_dir_detected(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        assert detect_target_kind(str(d)) == "starter_dir"

    def test_workflow_artifact_json_detected(self, tmp_path):
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(_make_valid_workflow_artifact()))
        assert detect_target_kind(str(p)) == "workflow_artifact"

    def test_nonexistent_path_returns_unknown(self):
        assert detect_target_kind("/nonexistent/path.yaml") == "unknown"

    def test_directory_missing_files_returns_unknown(self, tmp_path):
        d = tmp_path / "partial"
        d.mkdir()
        (d / "policy.yaml").write_text(MINIMAL_VALID_POLICY)
        assert detect_target_kind(str(d)) == "unknown"


# ---------------------------------------------------------------------------
# Policy lint
# ---------------------------------------------------------------------------

class TestLintPolicy:
    def test_valid_policy_returns_no_findings(self, tmp_path):
        p = _write(tmp_path, "policy.yaml", MINIMAL_VALID_POLICY)
        assert lint_policy(p) == []

    def test_malformed_yaml_returns_load_error(self, tmp_path):
        p = _write(tmp_path, "bad.yaml", "roles: [unclosed")
        findings = lint_policy(p)
        assert any(f["code"] == "POLICY_LOAD_ERROR" for f in findings)

    def test_non_mapping_yaml_returns_load_error(self, tmp_path):
        p = _write(tmp_path, "list.yaml", "- item1\n- item2\n")
        findings = lint_policy(p)
        assert any(f["code"] == "POLICY_LOAD_ERROR" for f in findings)

    def test_schema_violation_returns_schema_error(self, tmp_path):
        # policy_version is required by the schema
        p = _write(tmp_path, "noversionfield.yaml", "roles:\n  - ai-assistant\n")
        findings = lint_policy(p)
        assert any(f["code"] == "POLICY_SCHEMA_VALIDATION_ERROR" for f in findings)

    def test_date_inversion_returns_load_error(self, tmp_path):
        content = (
            MINIMAL_VALID_POLICY
            + "effective_date: '2030-01-01'\n"
            + "expiration_date: '2020-01-01'\n"
        )
        p = _write(tmp_path, "date_inv.yaml", content)
        findings = lint_policy(p)
        assert any(f["code"] == "POLICY_LOAD_ERROR" for f in findings)
        assert any("effective_date" in f["message"] for f in findings)

    def test_duplicate_allowed_tool_returns_finding(self, tmp_path):
        content = (
            MINIMAL_VALID_POLICY
            + "tools:\n"
            + "  allowed_tools:\n"
            + "    - name: search\n"
            + "      max_calls: 3\n"
            + "    - name: search\n"
            + "      max_calls: 5\n"
        )
        p = _write(tmp_path, "dup_tool.yaml", content)
        findings = lint_policy(p)
        assert any(f["code"] == "TOOL_CONSTRAINT_VIOLATION" for f in findings)
        assert any("search" in f["message"] for f in findings)

    def test_invalid_output_schema_returns_finding(self, tmp_path):
        content = (
            MINIMAL_VALID_POLICY
            + "output_schema:\n"
            + "  type: not-a-valid-json-schema-type\n"
        )
        p = _write(tmp_path, "bad_schema.yaml", content)
        findings = lint_policy(p)
        assert any(f["code"] == "POLICY_SCHEMA_VALIDATION_ERROR" for f in findings)

    def test_zero_max_calls_returns_schema_error(self, tmp_path):
        # max_calls has minimum: 1 in the DSL schema — zero surfaces as a schema error,
        # not TOOL_CONSTRAINT_VIOLATION, because the linter returns early on schema errors.
        content = (
            MINIMAL_VALID_POLICY
            + "tools:\n"
            + "  allowed_tools:\n"
            + "    - name: search\n"
            + "      max_calls: 0\n"
        )
        p = _write(tmp_path, "zero_max.yaml", content)
        findings = lint_policy(p)
        assert any(f["code"] == "POLICY_SCHEMA_VALIDATION_ERROR" for f in findings)

    def test_finding_has_required_keys(self, tmp_path):
        p = _write(tmp_path, "bad.yaml", "roles: [unclosed")
        findings = lint_policy(p)
        for f in findings:
            assert "code" in f
            assert "message" in f
            assert "target_kind" in f
            assert "path" in f

    def test_nonexistent_file_returns_load_error(self):
        findings = lint_policy("/nonexistent/policy.yaml")
        assert any(f["code"] == "POLICY_LOAD_ERROR" for f in findings)


# ---------------------------------------------------------------------------
# Starter directory lint
# ---------------------------------------------------------------------------

class TestLintStarterDir:
    def test_valid_starter_returns_no_findings(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        assert lint_starter_dir(str(d)) == []

    def test_missing_readme_returns_integrity_error(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        (d / "README.md").unlink()
        findings = lint_starter_dir(str(d))
        assert any(f["code"] == "WORKFLOW_STARTER_INTEGRITY_ERROR" for f in findings)
        assert any("README.md" in f["message"] for f in findings)

    def test_missing_policy_returns_integrity_error(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        (d / "policy.yaml").unlink()
        findings = lint_starter_dir(str(d))
        assert any(f["code"] == "WORKFLOW_STARTER_INTEGRITY_ERROR" for f in findings)

    def test_missing_workflow_py_returns_integrity_error(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        (d / "workflow_example.py").unlink()
        findings = lint_starter_dir(str(d))
        assert any(f["code"] == "WORKFLOW_STARTER_INTEGRITY_ERROR" for f in findings)

    def test_internal_import_returns_integrity_error(self, tmp_path):
        d = _make_starter_dir(tmp_path, internal_import=True)
        findings = lint_starter_dir(str(d))
        assert any(f["code"] == "WORKFLOW_STARTER_INTEGRITY_ERROR" for f in findings)
        assert any("_internal" in f["message"] for f in findings)

    def test_syntax_error_in_workflow_py_returns_integrity_error(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        (d / "workflow_example.py").write_text("def broken(\n")
        findings = lint_starter_dir(str(d))
        assert any(f["code"] == "WORKFLOW_STARTER_INTEGRITY_ERROR" for f in findings)

    def test_empty_file_returns_integrity_error(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        (d / "README.md").write_text("")
        findings = lint_starter_dir(str(d))
        assert any(f["code"] == "WORKFLOW_STARTER_INTEGRITY_ERROR" for f in findings)

    def test_invalid_nested_policy_propagates_error(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        (d / "policy.yaml").write_text("roles: [unclosed")
        findings = lint_starter_dir(str(d))
        assert findings


# ---------------------------------------------------------------------------
# Workflow artifact lint
# ---------------------------------------------------------------------------

class TestLintWorkflowArtifact:
    def test_valid_artifact_returns_no_findings(self, tmp_path):
        artifact = _make_valid_workflow_artifact()
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        assert lint_workflow_artifact(str(p)) == []

    def test_json_parse_error_returns_finding(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        findings = lint_workflow_artifact(str(p))
        assert findings
        assert any(f["code"] == "POLICY_LOAD_ERROR" for f in findings)

    def test_schema_violation_returns_finding(self, tmp_path):
        artifact = _make_valid_workflow_artifact()
        del artifact["session_id"]  # required field
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        findings = lint_workflow_artifact(str(p))
        assert any(f["code"] == "POLICY_SCHEMA_VALIDATION_ERROR" for f in findings)

    def test_checksum_step_mismatch_returns_finding(self, tmp_path):
        artifact = _make_valid_workflow_artifact(steps=2)
        artifact["invocation_audit_checksums"] = ["a" * 64]  # only 1, steps has 2
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        findings = lint_workflow_artifact(str(p))
        assert any(
            "invocation_audit_checksums" in f["message"] or "mismatch" in f["message"].lower()
            for f in findings
        )

    def test_failed_without_failure_summary_returns_finding(self, tmp_path):
        artifact = _make_valid_workflow_artifact(status="FAILED")
        artifact["failure_summary"] = None
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        findings = lint_workflow_artifact(str(p))
        assert any("FAILED" in f["message"] and "failure_summary" in f["message"] for f in findings)

    def test_completed_with_failure_summary_returns_finding(self, tmp_path):
        artifact = _make_valid_workflow_artifact(status="COMPLETED")
        artifact["failure_summary"] = {"exception_type": "SomeError", "message": "oops"}
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        findings = lint_workflow_artifact(str(p))
        assert any("failure_summary" in f["message"] for f in findings)


# ---------------------------------------------------------------------------
# lint_target (unified)
# ---------------------------------------------------------------------------

class TestLintTarget:
    def test_auto_detects_policy_yaml(self, tmp_path):
        p = _write(tmp_path, "policy.yaml", MINIMAL_VALID_POLICY)
        assert lint_target(p) == []

    def test_auto_detects_starter_dir(self, tmp_path):
        d = _make_starter_dir(tmp_path)
        assert lint_target(str(d)) == []

    def test_auto_detects_workflow_artifact(self, tmp_path):
        artifact = _make_valid_workflow_artifact()
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        assert lint_target(str(p)) == []

    def test_unknown_target_returns_finding(self, tmp_path):
        p = tmp_path / "file.txt"
        p.write_text("hello")
        findings = lint_target(str(p))
        assert findings
        assert any(f["code"] == "POLICY_LOAD_ERROR" for f in findings)

    def test_explicit_kind_overrides_auto(self, tmp_path):
        # Passing --kind policy on a YAML file is fine
        p = _write(tmp_path, "policy.yaml", MINIMAL_VALID_POLICY)
        assert lint_target(p, kind="policy") == []
