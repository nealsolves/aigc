"""
Tests for AuditLineage — DAG reconstruction from JSONL audit trails.

Verifies:
- Empty graph state
- add_artifact() and from_jsonl() loading
- DAG edge construction from derived_from_audit_checksums
- roots(), leaves(), ancestors(), descendants() traversal
- orphan detection
- cycle detection
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from aigc._internal.lineage import AuditLineage, _artifact_checksum


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_artifact(**kwargs) -> dict:
    """Minimal valid artifact. Override fields via kwargs."""
    base = {
        "audit_schema_version": "1.4",
        "policy_file": "test_policy.yaml",
        "policy_schema_version": "http://json-schema.org/draft-07/schema#",
        "policy_version": "1.0",
        "model_provider": "test_provider",
        "model_identifier": "test_model",
        "role": "tester",
        "enforcement_result": "PASS",
        "failures": [],
        "failure_gate": None,
        "failure_reason": None,
        "input_checksum": "a" * 64,
        "output_checksum": "b" * 64,
        "context": {},
        "timestamp": 1700000000,
        "metadata": {},
        "risk_score": None,
        "signature": None,
        "provenance": None,
    }
    base.update(kwargs)
    return base


def _write_jsonl(artifacts: list[dict], path: Path) -> None:
    with path.open("w") as f:
        for a in artifacts:
            f.write(json.dumps(a) + "\n")


# ---------------------------------------------------------------------------
# Empty graph
# ---------------------------------------------------------------------------

def test_empty_lineage_len_is_zero():
    assert len(AuditLineage()) == 0


def test_empty_lineage_roots_is_empty():
    assert AuditLineage().roots() == []


def test_empty_lineage_leaves_is_empty():
    assert AuditLineage().leaves() == []


def test_empty_lineage_orphans_is_empty():
    assert AuditLineage().orphans() == []


def test_empty_lineage_has_cycle_is_false():
    assert AuditLineage().has_cycle() is False


# ---------------------------------------------------------------------------
# add_artifact / get / len
# ---------------------------------------------------------------------------

def test_add_artifact_returns_checksum_string():
    lineage = AuditLineage()
    artifact = _make_artifact()
    key = lineage.add_artifact(artifact)
    assert isinstance(key, str)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_len_reflects_added_artifacts():
    lineage = AuditLineage()
    lineage.add_artifact(_make_artifact(input_checksum="a" * 64))
    lineage.add_artifact(_make_artifact(input_checksum="c" * 64))
    assert len(lineage) == 2


def test_get_returns_artifact_by_checksum():
    lineage = AuditLineage()
    artifact = _make_artifact()
    key = lineage.add_artifact(artifact)
    assert lineage.get(key) == artifact


def test_get_returns_none_for_unknown():
    lineage = AuditLineage()
    assert lineage.get("0" * 64) is None


# ---------------------------------------------------------------------------
# Single artifact (no provenance)
# ---------------------------------------------------------------------------

def test_artifact_without_provenance_is_root_and_leaf():
    lineage = AuditLineage()
    artifact = _make_artifact()
    lineage.add_artifact(artifact)
    assert artifact in lineage.roots()
    assert artifact in lineage.leaves()


# ---------------------------------------------------------------------------
# from_jsonl
# ---------------------------------------------------------------------------

def test_from_jsonl_loads_artifacts():
    a1 = _make_artifact(input_checksum="a" * 64)
    a2 = _make_artifact(input_checksum="b" * 64)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "trail.jsonl"
        _write_jsonl([a1, a2], path)
        lineage = AuditLineage.from_jsonl(path)
    assert len(lineage) == 2


def test_from_jsonl_empty_file_returns_empty_lineage():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "empty.jsonl"
        path.write_text("")
        lineage = AuditLineage.from_jsonl(path)
    assert len(lineage) == 0


# ---------------------------------------------------------------------------
# DAG edge construction
# ---------------------------------------------------------------------------

def test_parent_child_edge_built_from_provenance():
    lineage = AuditLineage()
    parent = _make_artifact(input_checksum="a" * 64)
    parent_key = lineage.add_artifact(parent)

    child = _make_artifact(
        input_checksum="b" * 64,
        provenance={"derived_from_audit_checksums": [parent_key]},
    )
    child_key = lineage.add_artifact(child)

    # parent is a root; child is a leaf
    assert parent in lineage.roots()
    assert child in lineage.leaves()
    assert parent not in lineage.leaves()
    assert child not in lineage.roots()
    assert lineage.get(child_key) == child


def test_roots_excludes_artifacts_with_parents():
    lineage = AuditLineage()
    root = _make_artifact(input_checksum="a" * 64)
    root_key = lineage.add_artifact(root)
    child = _make_artifact(
        input_checksum="b" * 64,
        provenance={"derived_from_audit_checksums": [root_key]},
    )
    lineage.add_artifact(child)
    assert lineage.roots() == [root]


def test_leaves_excludes_artifacts_with_children():
    lineage = AuditLineage()
    root = _make_artifact(input_checksum="a" * 64)
    root_key = lineage.add_artifact(root)
    child = _make_artifact(
        input_checksum="b" * 64,
        provenance={"derived_from_audit_checksums": [root_key]},
    )
    lineage.add_artifact(child)
    assert lineage.leaves() == [child]


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------

def test_ancestors_returns_all_upstream():
    """root -> mid -> leaf: leaf.ancestors() == [mid, root]"""
    lineage = AuditLineage()
    root = _make_artifact(input_checksum="a" * 64)
    root_key = lineage.add_artifact(root)
    mid = _make_artifact(
        input_checksum="b" * 64,
        provenance={"derived_from_audit_checksums": [root_key]},
    )
    mid_key = lineage.add_artifact(mid)
    leaf = _make_artifact(
        input_checksum="c" * 64,
        provenance={"derived_from_audit_checksums": [mid_key]},
    )
    leaf_key = lineage.add_artifact(leaf)

    result = lineage.ancestors(leaf_key)
    assert mid in result
    assert root in result
    assert leaf not in result


def test_descendants_returns_all_downstream():
    """root -> mid -> leaf: root.descendants() == [mid, leaf]"""
    lineage = AuditLineage()
    root = _make_artifact(input_checksum="a" * 64)
    root_key = lineage.add_artifact(root)
    mid = _make_artifact(
        input_checksum="b" * 64,
        provenance={"derived_from_audit_checksums": [root_key]},
    )
    mid_key = lineage.add_artifact(mid)
    leaf = _make_artifact(
        input_checksum="c" * 64,
        provenance={"derived_from_audit_checksums": [mid_key]},
    )
    lineage.add_artifact(leaf)

    result = lineage.descendants(root_key)
    assert mid in result
    assert leaf in result
    assert root not in result


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------

def test_orphan_is_detected():
    """Artifact referencing a checksum not in the graph is an orphan."""
    lineage = AuditLineage()
    orphan = _make_artifact(
        input_checksum="a" * 64,
        provenance={"derived_from_audit_checksums": ["f" * 64]},
    )
    lineage.add_artifact(orphan)
    assert orphan in lineage.orphans()


def test_no_orphans_in_complete_graph():
    lineage = AuditLineage()
    parent = _make_artifact(input_checksum="a" * 64)
    parent_key = lineage.add_artifact(parent)
    child = _make_artifact(
        input_checksum="b" * 64,
        provenance={"derived_from_audit_checksums": [parent_key]},
    )
    lineage.add_artifact(child)
    assert lineage.orphans() == []


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def test_has_cycle_true_when_cycle_injected():
    """
    Directly inject a cycle into the graph's internal state and confirm
    has_cycle() detects it.

    Constructing a cryptographic cycle through add_artifact() is impossible
    because each artifact's node key depends on its content, and including the
    other artifact's key in provenance changes that content (chicken-and-egg).
    Direct state injection is the correct way to test the cycle-detection
    algorithm in isolation.
    """
    lineage = AuditLineage()
    a = _make_artifact(input_checksum="a" * 64)
    b = _make_artifact(input_checksum="b" * 64)
    ka = lineage.add_artifact(a)
    kb = lineage.add_artifact(b)

    # Inject a->b and b->a edges directly
    lineage._parents[ka].append(kb)
    lineage._children[kb].append(ka)
    lineage._parents[kb].append(ka)
    lineage._children[ka].append(kb)

    assert lineage.has_cycle() is True
