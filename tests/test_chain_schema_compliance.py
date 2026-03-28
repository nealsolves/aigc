"""Integration tests: AuditChain → audit schema → compliance export.

These tests verify that artifacts produced by AuditChain.append() remain
valid against audit_artifact.schema.json and are accepted by the compliance
export CLI.  They guard against the schema incompatibility found in R030-002.
"""
from __future__ import annotations

import json

from jsonschema import validate as jsonschema_validate

from aigc._internal.audit import generate_audit_artifact
from aigc._internal.audit_chain import AuditChain
from aigc._internal.cli import main
from aigc._internal.policy_loader import SCHEMAS_DIR

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SCHEMA_PATH = SCHEMAS_DIR / "audit_artifact.schema.json"


def _audit_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _make_base_artifact(result: str = "PASS") -> dict:
    invocation = {
        "policy_file": "test.yaml",
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {"prompt": "hello"},
        "output": {"result": "ok"},
        "context": {},
    }
    return generate_audit_artifact(
        invocation,
        {"policy_version": "1.0"},
        enforcement_result=result,
        metadata={"gates_evaluated": ["guard_evaluation", "role_validation"]},
        timestamp=1_700_000_000,
    )


# ---------------------------------------------------------------------------
# Chain → schema compatibility
# ---------------------------------------------------------------------------

def test_chained_artifact_passes_audit_schema():
    """After AuditChain.append(), the artifact must be valid per audit_artifact.schema.json."""
    artifact = _make_base_artifact()
    chain = AuditChain()
    chained = chain.append(artifact)

    schema = _audit_schema()
    # Must not raise
    jsonschema_validate(instance=chained, schema=schema)


def test_multiple_chained_artifacts_all_pass_schema():
    """Every artifact in a multi-link chain must be schema-valid."""
    chain = AuditChain()
    schema = _audit_schema()
    for _ in range(3):
        chained = chain.append(_make_base_artifact())
        jsonschema_validate(instance=chained, schema=schema)


def test_chained_artifact_checksum_field_is_string():
    """The checksum field added by chain.append() must be a non-empty string."""
    artifact = _make_base_artifact()
    chain = AuditChain()
    chained = chain.append(artifact)

    assert "checksum" in chained
    assert isinstance(chained["checksum"], str)
    assert len(chained["checksum"]) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# Chain → compliance export CLI
# ---------------------------------------------------------------------------

def test_chained_artifact_accepted_by_compliance_export(tmp_path):
    """compliance export must count a chained artifact as valid (not invalid)."""
    artifact = _make_base_artifact()
    chain = AuditChain()
    chained = chain.append(artifact)

    jsonl_path = tmp_path / "chained.jsonl"
    jsonl_path.write_text(json.dumps(chained) + "\n", encoding="utf-8")

    output_path = tmp_path / "report.json"
    exit_code = main([
        "compliance", "export",
        "--input", str(jsonl_path),
        "--output", str(output_path),
    ])

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["total_artifacts"] == 1
    assert report["invalid_artifacts"] == 0
    assert report["pass_count"] == 1


def test_chained_fail_artifact_accepted_by_compliance_export(tmp_path):
    """A chained FAIL artifact is accepted and counted in fail_count."""
    artifact = _make_base_artifact(result="FAIL")
    chain = AuditChain()
    chained = chain.append(artifact)

    jsonl_path = tmp_path / "chained_fail.jsonl"
    jsonl_path.write_text(json.dumps(chained) + "\n", encoding="utf-8")

    output_path = tmp_path / "report.json"
    main([
        "compliance", "export",
        "--input", str(jsonl_path),
        "--output", str(output_path),
    ])

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["total_artifacts"] == 1
    assert report["invalid_artifacts"] == 0
    assert report["fail_count"] == 1
