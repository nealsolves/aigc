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
    assert lineage.checksum_of(artifact) == key


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


# ---------------------------------------------------------------------------
# Stored checksum field (AuditChain integration path)
# ---------------------------------------------------------------------------

def test_lineage_key_is_content_only_hash():
    """Lineage node key is sha256(artifact-without-chain-fields), not the stored checksum.

    AuditChain writes artifact['checksum'] = sha256(artifact_with_chain_fields).
    That value must NOT be used as the lineage key; otherwise checksum_of() returns
    different values before and after chain.append(), breaking derived_from references.
    """
    stored = "a" * 64
    artifact = _make_artifact(checksum=stored)
    lineage = AuditLineage()
    key = lineage.add_artifact(artifact)
    assert key != stored, "stored chain checksum must not be used as lineage node key"
    assert lineage.checksum_of(artifact) == key


def test_lineage_key_stable_when_chain_fields_present():
    """Adding chain fields to an artifact does not change its lineage key.

    AuditChain.append() adds chain_id, chain_index, previous_audit_checksum,
    and checksum.  All four are stripped before hashing, so checksum_of()
    returns the same digest before and after chaining.
    """
    artifact = _make_artifact()
    key_before = _artifact_checksum(artifact)

    # Simulate AuditChain.append() mutating the artifact in place.
    artifact["chain_id"] = "some-chain"
    artifact["chain_index"] = 0
    artifact["previous_audit_checksum"] = None
    artifact["checksum"] = "b" * 64  # chain-integrity hash, different from key

    key_after = _artifact_checksum(artifact)
    assert key_before == key_after, "lineage key must be invariant across chaining"


def test_lineage_edges_use_checksum_of_for_parent_reference():
    """Edges resolve when derived_from_audit_checksums uses checksum_of(parent).

    The integration contract: obtain parent checksums via checksum_of() (or
    lineage.add_artifact() return value), not by reading artifact['checksum'].
    """
    lineage = AuditLineage()
    parent = _make_artifact(input_checksum="a" * 64)
    parent_key = lineage.add_artifact(parent)
    assert parent_key == lineage.checksum_of(parent)

    child = _make_artifact(
        input_checksum="b" * 64,
        provenance={"derived_from_audit_checksums": [parent_key]},
    )
    child_key = lineage.add_artifact(child)

    assert parent in lineage.roots()
    assert child in lineage.leaves()
    assert parent in lineage.ancestors(child_key)
    assert child in lineage.descendants(parent_key)


# ---------------------------------------------------------------------------
# Duplicate-key topology reset
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Malformed JSONL input validation
# ---------------------------------------------------------------------------

def test_string_derived_from_checksums_raises_value_error():
    """derived_from_audit_checksums as a string must raise ValueError.

    If the persisted value is a bare string (e.g. "deadbeef"), iterating it
    yields individual characters, silently building a corrupt DAG.  The loader
    must reject this at call time rather than propagating wrong parent edges.
    """
    import pytest
    lineage = AuditLineage()
    artifact = _make_artifact(
        provenance={"derived_from_audit_checksums": "deadbeef"}
    )
    with pytest.raises(ValueError, match="derived_from_audit_checksums"):
        lineage.add_artifact(artifact)


def test_non_string_checksum_field_is_ignored():
    """A non-string checksum field is stripped and does not affect the lineage key.

    Under content-based keys, artifact['checksum'] is a chain-integrity field
    that is always excluded from hashing.  A malformed value (e.g. int 123)
    is stripped harmlessly; it does not propagate into _artifacts/_parents/_children
    as a non-string key.
    """
    lineage = AuditLineage()
    artifact = _make_artifact(checksum=123)
    key = lineage.add_artifact(artifact)
    assert isinstance(key, str)
    assert len(key) == 64


def test_non_string_element_in_checksums_list_raises_value_error():
    """Non-string element inside derived_from_audit_checksums must raise ValueError.

    A list like [123] passes the isinstance(raw_parents, list) guard but inserts
    an int as a parent key, poisoning _parents and _children with non-string entries
    that break all later str-keyed lookups.
    """
    import pytest
    lineage = AuditLineage()
    artifact = _make_artifact(
        provenance={"derived_from_audit_checksums": [123]}
    )
    with pytest.raises(ValueError, match="derived_from_audit_checksums"):
        lineage.add_artifact(artifact)


def test_add_artifact_re_add_idempotent():
    """Re-adding the same artifact does not duplicate edges.

    Under content-based keys, the same content always maps to the same key.
    Edges must be rebuilt consistently without duplication.
    """
    lineage = AuditLineage()
    parent = _make_artifact(input_checksum="a" * 64)
    parent_key = lineage.add_artifact(parent)
    child = _make_artifact(
        input_checksum="b" * 64,
        provenance={"derived_from_audit_checksums": [parent_key]},
    )
    child_key = lineage.add_artifact(child)

    # Re-add with identical content (same key, same edges).
    lineage.add_artifact(
        _make_artifact(
            input_checksum="b" * 64,
            provenance={"derived_from_audit_checksums": [parent_key]},
        )
    )

    assert lineage._parents[child_key].count(parent_key) == 1, \
        "parent edge must not be duplicated on re-add"
    assert lineage._children[parent_key].count(child_key) == 1, \
        "child back-edge must not be duplicated on re-add"


# ---------------------------------------------------------------------------
# Rollback invariant: failed add_artifact() must not mutate the graph
# ---------------------------------------------------------------------------

def test_failed_add_new_artifact_leaves_graph_unchanged():
    """add_artifact() with invalid provenance must not insert the node.

    Regression for the pre-validation order bug: mutations were applied before
    the ValueError checks, so a failed call could insert a bad node into
    _artifacts and leave _parents/_children in an inconsistent state.
    """
    import pytest
    lineage = AuditLineage()
    bad = _make_artifact(
        input_checksum="f" * 64,
        provenance={"derived_from_audit_checksums": "not-a-list"},
    )
    with pytest.raises(ValueError):
        lineage.add_artifact(bad)

    # Graph must be completely empty — the node must not have been inserted.
    assert len(lineage) == 0
    assert lineage._artifacts == {}
    assert lineage._parents == {}
    assert lineage._children == {}


# ---------------------------------------------------------------------------
# P1 regression: lineage key must be stable across AuditChain.append()
# ---------------------------------------------------------------------------

def test_lineage_key_stable_across_audit_chain_append():
    """Node key must not change when AuditChain.append() adds chain metadata.

    Workflow: host calls checksum_of(parent) BEFORE chaining to obtain the key
    used in a child's derived_from_audit_checksums.  After chain.append(parent),
    the parent's lineage key must be the same value so ancestors() / descendants()
    / orphans() all resolve the relationship correctly.
    """
    from aigc._internal.audit import generate_audit_artifact
    from aigc._internal.audit_chain import AuditChain

    invocation = {
        "policy_file": "test_policy.yaml",
        "model_provider": "test_provider",
        "model_identifier": "test_model",
        "role": "tester",
        "input": {},
        "output": {},
        "context": {},
    }
    policy = {"policy_version": "1.0"}

    parent = generate_audit_artifact(invocation, policy, timestamp=1700000000)

    # Capture key BEFORE chaining (simulates typical host provenance workflow)
    lineage = AuditLineage()
    pre_chain_key = lineage.checksum_of(parent)

    # Chain the parent — must not change its effective lineage key
    chain = AuditChain()
    chain.append(parent)

    # Generate child referencing the pre-chain key
    child_invocation = dict(invocation, input={"step": 2})
    child = generate_audit_artifact(
        child_invocation, policy,
        provenance={"derived_from_audit_checksums": [pre_chain_key]},
        timestamp=1700000001,
    )

    parent_key = lineage.add_artifact(parent)
    child_key = lineage.add_artifact(child)

    assert parent_key == pre_chain_key, (
        "AuditChain.append() must not shift the artifact's lineage node key; "
        f"pre-chain={pre_chain_key!r}, post-chain={parent_key!r}"
    )
    assert parent in lineage.ancestors(child_key), \
        "parent must appear in child's ancestors()"
    assert child in lineage.descendants(parent_key), \
        "child must appear in parent's descendants()"
    assert lineage.orphans() == [], \
        "child must not be an orphan when parent is present"


def test_failed_add_distinct_artifact_leaves_existing_edges_intact():
    """A failed add_artifact() for a distinct artifact must not corrupt existing edges.

    Under content-based keys, different provenance → different hash → distinct
    node.  A validation failure on a new node must never affect the edges of
    an already-present node.
    """
    import pytest
    lineage = AuditLineage()
    parent = _make_artifact(input_checksum="a" * 64)
    parent_key = lineage.add_artifact(parent)

    child = _make_artifact(
        input_checksum="b" * 64,
        provenance={"derived_from_audit_checksums": [parent_key]},
    )
    child_key = lineage.add_artifact(child)

    assert parent_key in lineage._parents[child_key]
    assert child_key in lineage._children[parent_key]

    # Attempt to add a different artifact with invalid provenance (int, not str).
    bad = _make_artifact(
        input_checksum="c" * 64,
        provenance={"derived_from_audit_checksums": [999]},
    )
    with pytest.raises(ValueError):
        lineage.add_artifact(bad)

    # Existing edges must still be intact.
    assert parent_key in lineage._parents[child_key], \
        "child-to-parent edge must survive a failed add of a distinct artifact"
    assert child_key in lineage._children[parent_key], \
        "parent-to-child back-edge must survive a failed add of a distinct artifact"
    assert len(lineage) == 2
