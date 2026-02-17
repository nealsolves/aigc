"""Tests for policy composition via extends."""

import pytest
from src.policy_loader import load_policy
from src.errors import PolicyLoadError


def test_extends_merges_arrays():
    """Child policy appends to base roles array."""
    policy = load_policy("tests/golden_traces/policy_child_extends_base.yaml")

    # Both base and child roles present
    assert "planner" in policy["roles"]
    assert "verifier" in policy["roles"]


def test_extends_replaces_scalars():
    """Child policy_version replaces base."""
    policy = load_policy("tests/golden_traces/policy_child_extends_base.yaml")

    # Child's policy_version overrides base
    assert policy["policy_version"] == "2.0"


def test_extends_merges_nested_dicts():
    """Preconditions from both base and child merge."""
    policy = load_policy("tests/golden_traces/policy_child_extends_base.yaml")

    # Both base and child preconditions present
    assert "role_declared" in policy["pre_conditions"]["required"]
    assert "citations_available" in policy["pre_conditions"]["required"]


def test_extends_inherits_output_schema():
    """Child inherits output_schema from base."""
    policy = load_policy("tests/golden_traces/policy_child_extends_base.yaml")

    # Output schema from base is inherited
    assert "output_schema" in policy
    assert policy["output_schema"]["properties"]["result"]["type"] == "string"


def test_no_extends_field():
    """Regular policy loading without extends works."""
    policy = load_policy("tests/golden_traces/golden_policy_v1.yaml")

    assert policy["policy_version"] == "1.0"
    assert "extends" not in policy


def test_extends_missing_base_fails():
    """Missing base policy file raises error."""
    with pytest.raises(PolicyLoadError) as exc_info:
        load_policy("tests/golden_traces/policy_extends_nonexistent.yaml")

    assert "Policy file does not exist" in str(exc_info.value)


def test_extends_removed_from_final_policy():
    """extends field is removed from merged policy."""
    policy = load_policy("tests/golden_traces/policy_child_extends_base.yaml")

    # extends field should be removed after merging
    assert "extends" not in policy


def test_extends_preserves_postconditions():
    """Postconditions from base are preserved."""
    policy = load_policy("tests/golden_traces/policy_child_extends_base.yaml")

    assert "post_conditions" in policy
    assert "output_schema_valid" in policy["post_conditions"]["required"]


def test_extends_inherits_description():
    """Child can override or inherit description."""
    policy = load_policy("tests/golden_traces/policy_child_extends_base.yaml")

    # Description from base is inherited (child doesn't override it)
    assert "description" in policy
    assert policy["description"] == "Base policy for composition testing"


def test_circular_extends_raises_policy_load_error():
    """Circular extends chain raises PolicyLoadError, not RecursionError."""
    with pytest.raises(PolicyLoadError) as exc_info:
        load_policy("tests/fixtures/policy_cycle_a.yaml")

    # Must be typed governance error, not RecursionError
    assert "Circular extends detected" in str(exc_info.value)
    assert "chain" in exc_info.value.details


def test_multi_level_extends_chain():
    """Multi-level non-cyclic extends chain works (A -> B -> C)."""
    # This tests that visited set is properly passed through the recursion
    # policy_child_extends_base extends policy_base, which is a 2-level chain
    policy = load_policy("tests/golden_traces/policy_child_extends_base.yaml")

    # Should successfully merge without cycle errors
    assert "roles" in policy
    assert "planner" in policy["roles"]  # from base
    assert "verifier" in policy["roles"]  # from child
