"""Golden replay tests for guard evaluation."""

import json
from aigc._internal.enforcement import enforce_invocation


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_golden_replay_guards_both_match():
    """Both guards match, postconditions and preconditions accumulate."""
    invocation = load_json("tests/golden_replays/golden_invocation_guards_match.json")

    audit = enforce_invocation(invocation)

    assert audit["enforcement_result"] == "PASS"
    assert audit["role"] == "planner"
    assert audit["model_provider"] == "anthropic"

    # Verify guards were evaluated
    guards_evaluated = audit["metadata"]["guards_evaluated"]
    assert len(guards_evaluated) == 2
    assert guards_evaluated[0]["condition"] == "is_enterprise"
    assert guards_evaluated[0]["matched"] is True
    assert guards_evaluated[1]["condition"] == "audit_enabled"
    assert guards_evaluated[1]["matched"] is True

    # Verify conditions were resolved
    conditions_resolved = audit["metadata"]["conditions_resolved"]
    assert conditions_resolved["is_enterprise"] is True
    assert conditions_resolved["audit_enabled"] is True

    # Verify preconditions include guard-added ones
    preconditions_satisfied = audit["metadata"]["preconditions_satisfied"]
    assert "role_declared" in preconditions_satisfied
    assert "schema_exists" in preconditions_satisfied
    assert "enterprise_quota_available" in preconditions_satisfied  # From guard 1
    assert "audit_log_configured" in preconditions_satisfied  # From guard 2

    # Verify schema validation passed
    assert audit["metadata"]["schema_validation"] == "passed"


def test_golden_replay_guards_partial_match():
    """One guard matches, only its effects applied."""
    invocation = load_json("tests/golden_replays/golden_invocation_guards_partial.json")

    audit = enforce_invocation(invocation)

    assert audit["enforcement_result"] == "PASS"

    # Verify guards were evaluated
    guards_evaluated = audit["metadata"]["guards_evaluated"]
    assert len(guards_evaluated) == 2
    assert guards_evaluated[0]["condition"] == "is_enterprise"
    assert guards_evaluated[0]["matched"] is True
    assert guards_evaluated[1]["condition"] == "audit_enabled"
    assert guards_evaluated[1]["matched"] is False

    # Verify conditions were resolved
    conditions_resolved = audit["metadata"]["conditions_resolved"]
    assert conditions_resolved["is_enterprise"] is True
    assert conditions_resolved["audit_enabled"] is False

    # Verify only first guard's precondition added
    preconditions_satisfied = audit["metadata"]["preconditions_satisfied"]
    assert "enterprise_quota_available" in preconditions_satisfied


def test_golden_replay_guards_none_match():
    """No guards match, policy unchanged."""
    invocation = load_json("tests/golden_replays/golden_invocation_guards_none.json")

    audit = enforce_invocation(invocation)

    assert audit["enforcement_result"] == "PASS"

    # Verify guards were evaluated but none matched
    guards_evaluated = audit["metadata"]["guards_evaluated"]
    assert len(guards_evaluated) == 2
    assert all(not g["matched"] for g in guards_evaluated)

    # Verify conditions were resolved
    conditions_resolved = audit["metadata"]["conditions_resolved"]
    assert conditions_resolved["is_enterprise"] is False
    assert conditions_resolved["audit_enabled"] is False

    # Verify only base preconditions present
    preconditions_satisfied = audit["metadata"]["preconditions_satisfied"]
    assert set(preconditions_satisfied) == {"role_declared", "schema_exists"}
