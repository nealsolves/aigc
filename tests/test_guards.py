"""Tests for guard evaluation engine."""

import pytest
from aigc._internal.guards import evaluate_guards, _merge_policy_blocks, _evaluate_condition_expression
from aigc._internal.errors import GuardEvaluationError, ConditionResolutionError


def test_guard_matches_boolean_condition():
    """Guard with boolean condition that matches."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "conditions": {
            "is_enterprise": {"type": "boolean", "default": False}
        },
        "guards": [
            {
                "when": {"condition": "is_enterprise"},
                "then": {
                    "post_conditions": {
                        "required": ["audit_level_high"]
                    }
                }
            }
        ]
    }
    context = {"is_enterprise": True}
    invocation = {"role": "planner"}

    effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
        policy, context, invocation
    )

    assert len(guards_evaluated) == 1
    assert guards_evaluated[0]["condition"] == "is_enterprise"
    assert guards_evaluated[0]["matched"] is True
    assert "post_conditions" in effective_policy
    assert "audit_level_high" in effective_policy["post_conditions"]["required"]
    assert conditions_resolved == {"is_enterprise": True}


def test_guard_no_match_boolean_condition():
    """Guard with boolean condition that doesn't match."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "conditions": {
            "is_enterprise": {"type": "boolean", "default": False}
        },
        "guards": [
            {
                "when": {"condition": "is_enterprise"},
                "then": {
                    "post_conditions": {
                        "required": ["audit_level_high"]
                    }
                }
            }
        ]
    }
    context = {"is_enterprise": False}
    invocation = {"role": "planner"}

    effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
        policy, context, invocation
    )

    assert len(guards_evaluated) == 1
    assert guards_evaluated[0]["condition"] == "is_enterprise"
    assert guards_evaluated[0]["matched"] is False
    # Policy unchanged (guard didn't match)
    assert effective_policy.get("post_conditions") is None
    assert conditions_resolved == {"is_enterprise": False}


def test_guard_matches_role_equality():
    """Guard with role equality check that matches."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner", "verifier"],
        "guards": [
            {
                "when": {"condition": "role == verifier"},
                "then": {
                    "pre_conditions": {
                        "required": ["citations_available"]
                    }
                }
            }
        ]
    }
    context = {}
    invocation = {"role": "verifier"}

    effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
        policy, context, invocation
    )

    assert len(guards_evaluated) == 1
    assert guards_evaluated[0]["condition"] == "role == verifier"
    assert guards_evaluated[0]["matched"] is True
    assert "pre_conditions" in effective_policy
    assert "citations_available" in effective_policy["pre_conditions"]["required"]


def test_guard_no_match_role_equality():
    """Guard with role equality check that doesn't match."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner", "verifier"],
        "guards": [
            {
                "when": {"condition": "role == verifier"},
                "then": {
                    "pre_conditions": {
                        "required": ["citations_available"]
                    }
                }
            }
        ]
    }
    context = {}
    invocation = {"role": "planner"}

    effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
        policy, context, invocation
    )

    assert len(guards_evaluated) == 1
    assert guards_evaluated[0]["condition"] == "role == verifier"
    assert guards_evaluated[0]["matched"] is False
    assert effective_policy.get("pre_conditions") is None


def test_guard_adds_preconditions():
    """Guard appends to existing preconditions array."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "pre_conditions": {
            "required": ["role_declared"]
        },
        "conditions": {
            "is_enterprise": {"type": "boolean"}
        },
        "guards": [
            {
                "when": {"condition": "is_enterprise"},
                "then": {
                    "pre_conditions": {
                        "required": ["audit_enabled"]
                    }
                }
            }
        ]
    }
    context = {"is_enterprise": True}
    invocation = {"role": "planner"}

    effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
        policy, context, invocation
    )

    # Both preconditions present (original + guard-added)
    assert set(effective_policy["pre_conditions"]["required"]) == {
        "role_declared",
        "audit_enabled",
    }


def test_guard_adds_postconditions():
    """Guard appends to existing postconditions array."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "post_conditions": {
            "required": ["output_schema_valid"]
        },
        "conditions": {
            "is_enterprise": {"type": "boolean"}
        },
        "guards": [
            {
                "when": {"condition": "is_enterprise"},
                "then": {
                    "post_conditions": {
                        "required": ["pii_redacted"]
                    }
                }
            }
        ]
    }
    context = {"is_enterprise": True}
    invocation = {"role": "planner"}

    effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
        policy, context, invocation
    )

    assert set(effective_policy["post_conditions"]["required"]) == {
        "output_schema_valid",
        "pii_redacted",
    }


def test_multiple_guards_accumulate():
    """Multiple guards both match and effects combine."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "conditions": {
            "is_enterprise": {"type": "boolean"},
            "audit_enabled": {"type": "boolean"}
        },
        "guards": [
            {
                "when": {"condition": "is_enterprise"},
                "then": {
                    "pre_conditions": {
                        "required": ["enterprise_quota"]
                    }
                }
            },
            {
                "when": {"condition": "audit_enabled"},
                "then": {
                    "post_conditions": {
                        "required": ["audit_written"]
                    }
                }
            }
        ]
    }
    context = {"is_enterprise": True, "audit_enabled": True}
    invocation = {"role": "planner"}

    effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
        policy, context, invocation
    )

    assert len(guards_evaluated) == 2
    assert all(g["matched"] for g in guards_evaluated)
    assert "enterprise_quota" in effective_policy["pre_conditions"]["required"]
    assert "audit_written" in effective_policy["post_conditions"]["required"]


def test_guard_order_matters():
    """Guards processed in declaration order."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "conditions": {
            "always_true": {"type": "boolean", "default": True}
        },
        "guards": [
            {
                "when": {"condition": "always_true"},
                "then": {"priority": 1}
            },
            {
                "when": {"condition": "always_true"},
                "then": {"priority": 2}  # Overrides first guard
            }
        ]
    }
    context = {}
    invocation = {"role": "planner"}

    effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
        policy, context, invocation
    )

    # Second guard's scalar replaces first guard's scalar
    assert effective_policy["priority"] == 2


def test_guard_unknown_condition():
    """Unknown condition in guard expression raises error."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "guards": [
            {
                "when": {"condition": "nonexistent_condition"},
                "then": {}
            }
        ]
    }
    context = {}
    invocation = {"role": "planner"}

    with pytest.raises(GuardEvaluationError) as exc_info:
        evaluate_guards(policy, context, invocation)

    assert exc_info.value.code == "GUARD_EVALUATION_ERROR"
    assert "nonexistent_condition" in str(exc_info.value)


def test_no_guards_returns_original_policy():
    """No guards in policy returns original policy unchanged."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"]
    }
    context = {}
    invocation = {"role": "planner"}

    effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
        policy, context, invocation
    )

    assert effective_policy == policy
    assert guards_evaluated == []
    assert conditions_resolved == {}


def test_guard_uses_default_condition():
    """Condition not in context uses default value."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "conditions": {
            "is_enterprise": {"type": "boolean", "default": False}
        },
        "guards": [
            {
                "when": {"condition": "is_enterprise"},
                "then": {
                    "post_conditions": {
                        "required": ["audit_level_high"]
                    }
                }
            }
        ]
    }
    context = {}  # No is_enterprise in context
    invocation = {"role": "planner"}

    effective_policy, guards_evaluated, conditions_resolved = evaluate_guards(
        policy, context, invocation
    )

    assert conditions_resolved == {"is_enterprise": False}
    assert guards_evaluated[0]["matched"] is False
    assert effective_policy.get("post_conditions") is None


def test_guard_with_required_condition_missing():
    """Required condition missing raises ConditionResolutionError."""
    policy = {
        "policy_version": "1.0",
        "roles": ["planner"],
        "conditions": {
            "audit_enabled": {"type": "boolean", "required": True}
        },
        "guards": [
            {
                "when": {"condition": "audit_enabled"},
                "then": {}
            }
        ]
    }
    context = {}  # Missing required condition
    invocation = {"role": "planner"}

    with pytest.raises(ConditionResolutionError) as exc_info:
        evaluate_guards(policy, context, invocation)

    assert exc_info.value.code == "CONDITION_RESOLUTION_ERROR"


def test_merge_policy_blocks_appends_arrays():
    """_merge_policy_blocks appends arrays."""
    base = {"roles": ["planner"]}
    overlay = {"roles": ["verifier"]}

    _merge_policy_blocks(base, overlay)

    assert base["roles"] == ["planner", "verifier"]


def test_merge_policy_blocks_replaces_scalars():
    """_merge_policy_blocks replaces scalar values."""
    base = {"policy_version": "1.0"}
    overlay = {"policy_version": "2.0"}

    _merge_policy_blocks(base, overlay)

    assert base["policy_version"] == "2.0"


def test_merge_policy_blocks_recursive_dicts():
    """_merge_policy_blocks recursively merges nested dicts."""
    base = {"pre_conditions": {"required": ["role_declared"]}}
    overlay = {"pre_conditions": {"required": ["schema_exists"]}}

    _merge_policy_blocks(base, overlay)

    assert base["pre_conditions"]["required"] == ["role_declared", "schema_exists"]


def test_evaluate_condition_expression_unsupported_equality():
    """Unsupported equality expression raises error."""
    with pytest.raises(GuardEvaluationError) as exc_info:
        _evaluate_condition_expression(
            "model == gpt-4",  # Unsupported left side
            {},
            {"role": "planner"}
        )

    assert exc_info.value.code == "GUARD_EVALUATION_ERROR"
    assert "Unsupported equality expression" in str(exc_info.value)
