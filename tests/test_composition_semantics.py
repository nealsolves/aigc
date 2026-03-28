"""Tests for composition restriction semantics (M2 feature)."""
import pytest

from aigc._internal.policy_loader import (
    _merge_policies,
    load_policy,
    COMPOSITION_INTERSECT,
    COMPOSITION_UNION,
    COMPOSITION_REPLACE,
    VALID_COMPOSITION_STRATEGIES,
)
from aigc._internal.errors import PolicyValidationError


# ── Default merge (backward compatible) ──────────────────────────


def test_default_merge_arrays_append():
    base = {"roles": ["a", "b"]}
    overlay = {"roles": ["c"]}
    merged = _merge_policies(base, overlay)
    assert merged["roles"] == ["a", "b", "c"]


def test_default_merge_dicts_recursive():
    base = {"pre_conditions": {"required": {"x": {"type": "string"}}}}
    overlay = {"pre_conditions": {"required": {"y": {"type": "number"}}}}
    merged = _merge_policies(base, overlay)
    assert "x" in merged["pre_conditions"]["required"]
    assert "y" in merged["pre_conditions"]["required"]


def test_default_merge_scalars_replace():
    base = {"policy_version": "1.0"}
    overlay = {"policy_version": "2.0"}
    merged = _merge_policies(base, overlay)
    assert merged["policy_version"] == "2.0"


# ── Intersect strategy ───────────────────────────────────────────


def test_intersect_arrays():
    base = {"roles": ["a", "b", "c"]}
    overlay = {"roles": ["b", "c", "d"]}
    merged = _merge_policies(base, overlay, COMPOSITION_INTERSECT)
    assert merged["roles"] == ["b", "c"]


def test_intersect_preserves_base_order():
    base = {"roles": ["c", "b", "a"]}
    overlay = {"roles": ["a", "c"]}
    merged = _merge_policies(base, overlay, COMPOSITION_INTERSECT)
    assert merged["roles"] == ["c", "a"]


def test_intersect_empty_result():
    base = {"roles": ["a"]}
    overlay = {"roles": ["b"]}
    merged = _merge_policies(base, overlay, COMPOSITION_INTERSECT)
    assert merged["roles"] == []


def test_intersect_dicts_recursive():
    base = {"pre_conditions": {"required": {"x": {"type": "string"}}}}
    overlay = {"pre_conditions": {"required": {"y": {"type": "number"}}}}
    merged = _merge_policies(base, overlay, COMPOSITION_INTERSECT)
    assert "x" in merged["pre_conditions"]["required"]
    assert "y" in merged["pre_conditions"]["required"]


# ── Union strategy ───────────────────────────────────────────────


def test_union_arrays_deduplicated():
    base = {"roles": ["a", "b"]}
    overlay = {"roles": ["b", "c"]}
    merged = _merge_policies(base, overlay, COMPOSITION_UNION)
    assert merged["roles"] == ["a", "b", "c"]


def test_union_preserves_order():
    base = {"roles": ["c", "a"]}
    overlay = {"roles": ["b", "a"]}
    merged = _merge_policies(base, overlay, COMPOSITION_UNION)
    assert merged["roles"] == ["c", "a", "b"]


def test_union_empty_base():
    base = {"roles": []}
    overlay = {"roles": ["a", "b"]}
    merged = _merge_policies(base, overlay, COMPOSITION_UNION)
    assert merged["roles"] == ["a", "b"]


# ── Replace strategy ────────────────────────────────────────────


def test_replace_completely_overrides():
    base = {"roles": ["a", "b"], "policy_version": "1.0"}
    overlay = {"roles": ["x"], "policy_version": "2.0"}
    merged = _merge_policies(base, overlay, COMPOSITION_REPLACE)
    assert merged["roles"] == ["x"]
    assert merged["policy_version"] == "2.0"


def test_replace_preserves_base_only_keys():
    base = {"roles": ["a"], "description": "base only"}
    overlay = {"roles": ["x"]}
    merged = _merge_policies(base, overlay, COMPOSITION_REPLACE)
    assert merged["description"] == "base only"
    assert merged["roles"] == ["x"]


# ── Composition strategy field handling ──────────────────────────


def test_composition_strategy_not_in_merged():
    base = {"roles": ["a"]}
    overlay = {"roles": ["b"], "composition_strategy": "union"}
    merged = _merge_policies(base, overlay, COMPOSITION_UNION)
    assert "composition_strategy" not in merged


def test_extends_not_in_merged():
    base = {"roles": ["a"]}
    overlay = {"roles": ["b"], "extends": "base.yaml"}
    merged = _merge_policies(base, overlay)
    assert "extends" not in merged


# ── Integration with extends ────────────────────────────────────


def test_load_policy_union(tmp_path):
    base = tmp_path / "base.yaml"
    base.write_text(
        "policy_version: '1.0'\nroles:\n  - planner\n  - verifier\n  - reviewer\n"
    )
    child = tmp_path / "child.yaml"
    child.write_text(
        "policy_version: '2.0'\n"
        "extends: base.yaml\n"
        "composition_strategy: union\n"
        "roles:\n  - planner\n  - reviewer\n"
    )
    policy = load_policy(str(child))
    assert "planner" in policy["roles"]
    assert "verifier" in policy["roles"]
    assert "reviewer" in policy["roles"]
    # Union deduplicates
    assert len(policy["roles"]) == len(set(policy["roles"]))


def test_load_policy_intersect(tmp_path):
    base = tmp_path / "base.yaml"
    base.write_text(
        "policy_version: '1.0'\nroles:\n  - planner\n  - verifier\n"
    )
    child = tmp_path / "child.yaml"
    child.write_text(
        "policy_version: '2.0'\n"
        "extends: base.yaml\n"
        "composition_strategy: intersect\n"
        "roles:\n  - planner\n"
    )
    policy = load_policy(str(child))
    assert policy["roles"] == ["planner"]


def test_load_policy_replace_escalation_raises(tmp_path):
    """replace strategy that adds roles absent from base raises PolicyValidationError."""
    base = tmp_path / "base.yaml"
    base.write_text(
        "policy_version: '1.0'\nroles:\n  - planner\n  - verifier\n"
    )
    child = tmp_path / "child.yaml"
    child.write_text(
        "policy_version: '2.0'\n"
        "extends: base.yaml\n"
        "composition_strategy: replace\n"
        "roles:\n  - admin\n"
    )
    with pytest.raises(PolicyValidationError, match="Composition escalation"):
        load_policy(str(child))


def test_load_policy_replace_valid_subset(tmp_path):
    """replace strategy that restricts to a subset of base roles is allowed."""
    base = tmp_path / "base.yaml"
    base.write_text(
        "policy_version: '1.0'\nroles:\n  - planner\n  - verifier\n"
    )
    child = tmp_path / "child.yaml"
    child.write_text(
        "policy_version: '2.0'\n"
        "extends: base.yaml\n"
        "composition_strategy: replace\n"
        "roles:\n  - planner\n"
    )
    policy = load_policy(str(child))
    assert policy["roles"] == ["planner"]


def test_union_role_escalation_raises(tmp_path):
    """union strategy that adds a role not in base raises PolicyValidationError."""
    base = tmp_path / "base.yaml"
    base.write_text("policy_version: '1.0'\nroles:\n  - planner\n")
    child = tmp_path / "child.yaml"
    child.write_text(
        "policy_version: '2.0'\n"
        "extends: base.yaml\n"
        "composition_strategy: union\n"
        "roles:\n  - admin\n"
    )
    with pytest.raises(PolicyValidationError, match="Composition escalation"):
        load_policy(str(child))


def test_intersect_postcondition_weakening_raises(tmp_path):
    """intersect that removes a required postcondition raises PolicyValidationError."""
    base = tmp_path / "base.yaml"
    base.write_text(
        "policy_version: '1.0'\n"
        "roles:\n  - planner\n"
        "post_conditions:\n"
        "  required:\n"
        "    - output_schema_valid\n"
    )
    child = tmp_path / "child.yaml"
    child.write_text(
        "policy_version: '2.0'\n"
        "extends: base.yaml\n"
        "composition_strategy: intersect\n"
        "post_conditions:\n"
        "  required: []\n"
    )
    with pytest.raises(PolicyValidationError, match="Composition weakening"):
        load_policy(str(child))


def test_invalid_composition_strategy(tmp_path):
    base = tmp_path / "base.yaml"
    base.write_text(
        "policy_version: '1.0'\nroles:\n  - planner\n"
    )
    child = tmp_path / "child.yaml"
    child.write_text(
        "policy_version: '2.0'\n"
        "extends: base.yaml\n"
        "composition_strategy: invalid\n"
        "roles:\n  - admin\n"
    )
    with pytest.raises(PolicyValidationError, match="Invalid composition_strategy"):
        load_policy(str(child))


# ── Determinism ──────────────────────────────────────────────────


def test_merge_deterministic():
    base = {"roles": ["a", "b"], "policy_version": "1.0"}
    overlay = {"roles": ["c"]}
    r1 = _merge_policies(base, overlay, COMPOSITION_UNION)
    r2 = _merge_policies(base, overlay, COMPOSITION_UNION)
    assert r1 == r2
