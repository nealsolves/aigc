"""Tests for compliance export CLI (M2 feature)."""
import json
import pytest
from pathlib import Path

from aigc._internal.cli import main, _cmd_compliance_export
from aigc._internal.audit import generate_audit_artifact


def _make_artifact(result="PASS", **kwargs):
    inv = {
        "policy_file": "test.yaml",
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {"prompt": "test"},
        "output": {"result": "ok"},
        "context": {},
    }
    return generate_audit_artifact(
        inv,
        {"policy_version": "1.0"},
        enforcement_result=result,
        metadata={"gates_evaluated": []},
        timestamp=1000,
        **kwargs,
    )


def _write_jsonl(path: Path, artifacts: list[dict]):
    with open(path, "w", encoding="utf-8") as f:
        for a in artifacts:
            f.write(json.dumps(a) + "\n")


# ── CLI interface ────────────────────────────────────────────────


def test_compliance_export_basic(tmp_path):
    """Basic compliance export produces valid JSON report."""
    artifacts = [
        _make_artifact("PASS"),
        _make_artifact("PASS"),
        _make_artifact("FAIL", failure_gate="role_validation",
                       failure_reason="bad role"),
    ]
    input_file = tmp_path / "audit.jsonl"
    _write_jsonl(input_file, artifacts)

    output_file = tmp_path / "report.json"
    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--output", str(output_file),
    ])
    assert exit_code == 0
    assert output_file.exists()

    report = json.loads(output_file.read_text())
    assert report["total_artifacts"] == 3
    assert report["pass_count"] == 2
    assert report["fail_count"] == 1
    assert report["compliance_rate"] == pytest.approx(66.67, abs=0.01)
    assert "role_validation" in report["failure_gates_summary"]


def test_compliance_export_to_stdout(tmp_path, capsys):
    artifacts = [_make_artifact("PASS")]
    input_file = tmp_path / "audit.jsonl"
    _write_jsonl(input_file, artifacts)

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
    ])
    assert exit_code == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["total_artifacts"] == 1


def test_compliance_export_missing_file():
    exit_code = main([
        "compliance", "export",
        "--input", "/nonexistent/file.jsonl",
    ])
    assert exit_code == 1


def test_compliance_export_empty_file(tmp_path):
    input_file = tmp_path / "empty.jsonl"
    input_file.write_text("")
    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
    ])
    assert exit_code == 0


def test_compliance_export_invalid_json_lines(tmp_path):
    """Invalid JSON lines are counted but don't crash."""
    input_file = tmp_path / "mixed.jsonl"
    content = json.dumps(_make_artifact("PASS")) + "\n"
    content += "not valid json\n"
    content += json.dumps({"incomplete": True}) + "\n"
    input_file.write_text(content)

    output_file = tmp_path / "report.json"
    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--output", str(output_file),
    ])
    assert exit_code == 0
    report = json.loads(output_file.read_text())
    assert report["total_artifacts"] == 1
    assert report["invalid_artifacts"] == 2


def test_compliance_export_with_artifacts(tmp_path):
    """--include-artifacts flag includes individual artifacts."""
    artifacts = [_make_artifact("PASS")]
    input_file = tmp_path / "audit.jsonl"
    _write_jsonl(input_file, artifacts)

    output_file = tmp_path / "report.json"
    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--output", str(output_file),
        "--include-artifacts",
    ])
    assert exit_code == 0
    report = json.loads(output_file.read_text())
    assert "artifacts" in report
    assert len(report["artifacts"]) == 1


def test_compliance_export_policy_summary(tmp_path):
    """Report includes per-policy summary."""
    artifacts = [
        _make_artifact("PASS"),
        _make_artifact("FAIL", failure_gate="role_validation",
                       failure_reason="bad"),
    ]
    input_file = tmp_path / "audit.jsonl"
    _write_jsonl(input_file, artifacts)

    output_file = tmp_path / "report.json"
    main([
        "compliance", "export",
        "--input", str(input_file),
        "--output", str(output_file),
    ])
    report = json.loads(output_file.read_text())
    assert len(report["policies"]) == 1
    assert report["policies"][0]["pass_count"] == 1
    assert report["policies"][0]["fail_count"] == 1


def test_compliance_report_version(tmp_path):
    artifacts = [_make_artifact("PASS")]
    input_file = tmp_path / "audit.jsonl"
    _write_jsonl(input_file, artifacts)

    output_file = tmp_path / "report.json"
    main([
        "compliance", "export",
        "--input", str(input_file),
        "--output", str(output_file),
    ])
    report = json.loads(output_file.read_text())
    assert report["compliance_report_version"] == "1.0"


def test_compliance_export_all_invalid_returns_nonzero(tmp_path):
    """Exit 1 when every artifact in the input fails schema validation."""
    # Write a single structurally-valid JSON object that is NOT a valid artifact
    input_file = tmp_path / "bad.jsonl"
    input_file.write_text(json.dumps({"not": "an artifact"}) + "\n")

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
    ])
    assert exit_code == 1


def test_compliance_export_partial_invalid_still_exits_zero(tmp_path):
    """Exit 0 when at least one artifact is valid, even if others are invalid."""
    artifacts = [_make_artifact("PASS")]
    input_file = tmp_path / "mixed.jsonl"
    with open(input_file, "w") as f:
        f.write(json.dumps(artifacts[0]) + "\n")
        f.write(json.dumps({"bad": "object"}) + "\n")

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
    ])
    assert exit_code == 0
