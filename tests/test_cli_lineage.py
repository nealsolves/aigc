"""Tests for --lineage flag in aigc compliance export (PR-04)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aigc._internal.cli import main
from aigc._internal.audit import generate_audit_artifact
from aigc._internal.lineage import _artifact_checksum


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_artifact(uid: str = "A", provenance=None) -> dict:
    """
    Schema-valid audit artifact distinguished by uid.
    Different uid values produce different input_checksum → different node keys.
    """
    inv = {
        "policy_file": "test.yaml",
        "model_provider": "test_provider",
        "model_identifier": "test_model",
        "role": "tester",
        "input": {"uid": uid},
        "output": {"result": uid},
        "context": {},
    }
    return generate_audit_artifact(
        inv,
        {"policy_version": "1.0"},
        enforcement_result="PASS",
        metadata={},
        timestamp=1000,
        provenance=provenance,
    )


def _write_jsonl(path: Path, artifacts: list[dict]) -> None:
    with path.open("w") as f:
        for a in artifacts:
            f.write(json.dumps(a) + "\n")


# ---------------------------------------------------------------------------
# Test 1: --lineage flag adds "lineage" key to report
# ---------------------------------------------------------------------------

def test_lineage_flag_adds_lineage_section(tmp_path):
    """--lineage produces report with a 'lineage' key containing expected fields."""
    artifact = _make_artifact("A")
    input_file = tmp_path / "trail.jsonl"
    _write_jsonl(input_file, [artifact])

    output_file = tmp_path / "report.json"
    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--output", str(output_file),
        "--lineage",
    ])
    assert exit_code == 0
    report = json.loads(output_file.read_text())
    assert "lineage" in report
    lineage = report["lineage"]
    assert "total_nodes" in lineage
    assert "root_count" in lineage
    assert "leaf_count" in lineage
    assert "orphan_count" in lineage
    assert "has_cycle" in lineage
    assert "roots" in lineage
    assert "leaves" in lineage
    assert "orphans" in lineage


# ---------------------------------------------------------------------------
# Test 2: No provenance → all artifacts are roots and leaves
# ---------------------------------------------------------------------------

def test_lineage_no_provenance_all_roots(tmp_path, capsys):
    """3 artifacts with no provenance: all are roots and leaves, no orphans, no cycle."""
    artifacts = [_make_artifact(uid) for uid in ["A", "B", "C"]]
    input_file = tmp_path / "trail.jsonl"
    _write_jsonl(input_file, artifacts)

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--lineage",
    ])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    lin = report["lineage"]
    assert lin["total_nodes"] == 3
    assert lin["root_count"] == 3
    assert lin["leaf_count"] == 3
    assert lin["orphan_count"] == 0
    assert lin["has_cycle"] is False


# ---------------------------------------------------------------------------
# Test 3: Single parent→child chain
# ---------------------------------------------------------------------------

def test_lineage_single_parent_child_chain(tmp_path, capsys):
    """A→B chain: A is root (no parents), B is leaf (no children)."""
    a = _make_artifact("A")
    key_a = _artifact_checksum(a)
    b = _make_artifact(
        "B",
        provenance={"derived_from_audit_checksums": [key_a]},
    )
    input_file = tmp_path / "trail.jsonl"
    _write_jsonl(input_file, [a, b])

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--lineage",
    ])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    lin = report["lineage"]
    assert lin["total_nodes"] == 2
    assert lin["root_count"] == 1
    assert lin["leaf_count"] == 1
    assert lin["orphan_count"] == 0
    assert key_a in lin["roots"]


# ---------------------------------------------------------------------------
# Test 4: Orphan detection
# ---------------------------------------------------------------------------

def test_lineage_orphan_detected(tmp_path, capsys):
    """Artifact referencing a missing parent checksum is reported as an orphan."""
    missing_key = "d" * 64  # unknown checksum
    a = _make_artifact(
        "A",
        provenance={"derived_from_audit_checksums": [missing_key]},
    )
    key_a = _artifact_checksum(a)
    input_file = tmp_path / "trail.jsonl"
    _write_jsonl(input_file, [a])

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--lineage",
    ])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    lin = report["lineage"]
    assert lin["orphan_count"] == 1
    assert key_a in lin["orphans"]
    # An orphan has a declared-but-missing parent — it is NOT a root
    assert lin["root_count"] == 0
    assert key_a not in lin["roots"]


# ---------------------------------------------------------------------------
# Test 5: has_cycle is False for a valid DAG
# ---------------------------------------------------------------------------

def test_lineage_has_cycle_false_for_valid_dag(tmp_path, capsys):
    """3-node chain A→B→C: has_cycle is False."""
    a = _make_artifact("A")
    key_a = _artifact_checksum(a)
    b = _make_artifact("B", provenance={"derived_from_audit_checksums": [key_a]})
    key_b = _artifact_checksum(b)
    c = _make_artifact("C", provenance={"derived_from_audit_checksums": [key_b]})
    input_file = tmp_path / "trail.jsonl"
    _write_jsonl(input_file, [a, b, c])

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--lineage",
    ])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["lineage"]["has_cycle"] is False
    assert report["lineage"]["total_nodes"] == 3
    assert report["lineage"]["root_count"] == 1
    assert report["lineage"]["leaf_count"] == 1


# ---------------------------------------------------------------------------
# Test 6: Empty file → zero counts
# ---------------------------------------------------------------------------

def test_lineage_empty_file_zero_counts(tmp_path, capsys):
    """Empty JSONL: lineage section has all-zero counts."""
    input_file = tmp_path / "empty.jsonl"
    input_file.write_text("")

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--lineage",
    ])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    lin = report["lineage"]
    assert lin["total_nodes"] == 0
    assert lin["root_count"] == 0
    assert lin["leaf_count"] == 0
    assert lin["orphan_count"] == 0
    assert lin["has_cycle"] is False
    assert lin["roots"] == []
    assert lin["leaves"] == []
    assert lin["orphans"] == []


# ---------------------------------------------------------------------------
# Test 7: --lineage --output writes lineage to file
# ---------------------------------------------------------------------------

def test_lineage_to_file_includes_lineage(tmp_path):
    """--lineage writes lineage section to output file."""
    input_file = tmp_path / "trail.jsonl"
    _write_jsonl(input_file, [_make_artifact("A"), _make_artifact("B")])

    output_file = tmp_path / "report.json"
    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--output", str(output_file),
        "--lineage",
    ])
    assert exit_code == 0
    assert output_file.exists()
    report = json.loads(output_file.read_text())
    assert "lineage" in report
    assert report["lineage"]["total_nodes"] == 2


# ---------------------------------------------------------------------------
# Test 8: Existing compliance fields preserved alongside lineage
# ---------------------------------------------------------------------------

def test_lineage_compliance_fields_preserved(tmp_path, capsys):
    """--lineage does not remove standard compliance report fields."""
    artifacts = [_make_artifact("A"), _make_artifact("B")]
    input_file = tmp_path / "trail.jsonl"
    _write_jsonl(input_file, artifacts)

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--lineage",
    ])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["compliance_report_version"] == "1.0"
    assert report["total_artifacts"] == 2
    assert report["pass_count"] == 2
    assert report["fail_count"] == 0
    assert "policies" in report
    assert "lineage" in report


# ---------------------------------------------------------------------------
# Test 9: Schema-invalid lines excluded from lineage count
# ---------------------------------------------------------------------------

def test_lineage_excludes_schema_invalid_artifacts(tmp_path, capsys):
    """total_nodes equals total_artifacts, not the raw line count.

    Pins the invariant that lineage is built from the already schema-validated
    artifacts list, not raw JSONL. A buggy implementation that called
    AuditLineage.from_jsonl() directly would include the invalid line and
    produce total_nodes=2 instead of total_nodes=1.
    """
    valid = _make_artifact("A")
    input_file = tmp_path / "trail.jsonl"
    with input_file.open("w") as f:
        f.write(json.dumps(valid) + "\n")
        f.write(json.dumps({"not": "an artifact"}) + "\n")  # schema-invalid

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--lineage",
    ])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["total_artifacts"] == 1
    assert report["invalid_artifacts"] == 1
    # Lineage node count must match validated artifact count minus duplicates.
    # No duplicates in this trail, so duplicate_artifacts == 0 and the counts
    # are equal — proving lineage is built from schema-valid artifacts only.
    assert report["lineage"]["duplicate_artifacts"] == 0
    assert report["lineage"]["total_nodes"] == (
        report["total_artifacts"] - report["lineage"]["duplicate_artifacts"]
    )
    assert report["lineage"]["total_nodes"] == 1


# ---------------------------------------------------------------------------
# Test 10: Stored checksum (AuditChain path) used as node key
# ---------------------------------------------------------------------------

def test_lineage_stored_checksum_used_as_node_key(tmp_path, capsys):
    """When an artifact has a stored 'checksum' field (AuditChain path),
    that value is used as the node key in roots/leaves — not the fallback
    sha256(canonical_json(artifact)).

    Pins the AuditLineage._artifact_checksum() branch at lineage.py:28.
    A regression that ignored the stored field would emit a different hash
    in roots[], causing downstream callers that already have the stored
    checksum to fail to cross-reference.
    """
    stored_key = "e" * 64  # simulates a checksum stamped by AuditChain
    parent = _make_artifact("parent")
    parent["checksum"] = stored_key  # AuditChain stamps this field

    child = _make_artifact(
        "child",
        provenance={"derived_from_audit_checksums": [stored_key]},
    )

    input_file = tmp_path / "trail.jsonl"
    _write_jsonl(input_file, [parent, child])

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--lineage",
    ])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    lin = report["lineage"]
    # The stored checksum must appear in roots — not a fallback sha256
    assert stored_key in lin["roots"]
    assert lin["root_count"] == 1
    assert lin["leaf_count"] == 1
    assert lin["orphan_count"] == 0


# ---------------------------------------------------------------------------
# Test 11: Duplicate artifacts reported in lineage.duplicate_artifacts
# ---------------------------------------------------------------------------

def test_lineage_duplicate_artifacts_counted(tmp_path, capsys):
    """Two identical valid artifacts deduplicate to one lineage node.

    total_artifacts counts all schema-valid lines; total_nodes counts unique
    checksums. duplicate_artifacts = total_artifacts - total_nodes makes the
    discrepancy explicit so callers can distinguish a 'clean' trail (no
    duplicates) from one with repeated artifacts.
    """
    artifact = _make_artifact("A")
    input_file = tmp_path / "trail.jsonl"
    _write_jsonl(input_file, [artifact, artifact])  # two identical lines

    exit_code = main([
        "compliance", "export",
        "--input", str(input_file),
        "--lineage",
    ])
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["total_artifacts"] == 2
    lin = report["lineage"]
    assert lin["total_nodes"] == 1
    assert lin["duplicate_artifacts"] == 1
    assert lin["total_nodes"] == report["total_artifacts"] - lin["duplicate_artifacts"]
