"""Tests for named condition resolution."""

import pytest
from aigc._internal.conditions import resolve_conditions
from aigc._internal.errors import ConditionResolutionError


def test_resolve_condition_from_context():
    """Resolve a simple boolean condition from context."""
    policy = {
        "conditions": {
            "is_enterprise": {"type": "boolean"}
        }
    }
    context = {"is_enterprise": True}

    resolved = resolve_conditions(policy, context)

    assert resolved == {"is_enterprise": True}


def test_resolve_condition_with_default():
    """Use default when condition not in context."""
    policy = {
        "conditions": {
            "is_enterprise": {"type": "boolean", "default": False}
        }
    }
    context = {}

    resolved = resolve_conditions(policy, context)

    assert resolved == {"is_enterprise": False}


def test_resolve_condition_required_missing():
    """Raise error when required condition missing from context."""
    policy = {
        "conditions": {
            "audit_enabled": {"type": "boolean", "required": True}
        }
    }
    context = {}

    with pytest.raises(ConditionResolutionError) as exc_info:
        resolve_conditions(policy, context)

    assert exc_info.value.code == "CONDITION_RESOLUTION_ERROR"
    assert exc_info.value.details["condition"] == "audit_enabled"
    assert exc_info.value.details["required"] is True


def test_resolve_condition_wrong_type():
    """Raise error when condition value is not boolean."""
    policy = {
        "conditions": {
            "is_enterprise": {"type": "boolean"}
        }
    }
    context = {"is_enterprise": "yes"}  # Wrong type

    with pytest.raises(ConditionResolutionError) as exc_info:
        resolve_conditions(policy, context)

    assert exc_info.value.code == "CONDITION_RESOLUTION_ERROR"
    assert exc_info.value.details["condition"] == "is_enterprise"
    assert exc_info.value.details["value_type"] == "str"


def test_resolve_multiple_conditions():
    """Resolve multiple conditions with mixed sources."""
    policy = {
        "conditions": {
            "is_enterprise": {"type": "boolean", "default": False},
            "audit_enabled": {"type": "boolean", "required": True},
            "premium_features": {"type": "boolean"}
        }
    }
    context = {
        "is_enterprise": True,  # Override default
        "audit_enabled": True,  # Required, provided
        "premium_features": False  # Provided
    }

    resolved = resolve_conditions(policy, context)

    assert resolved == {
        "is_enterprise": True,
        "audit_enabled": True,
        "premium_features": False
    }


def test_resolve_empty_conditions_block():
    """Return empty dict when conditions block is empty."""
    policy = {"conditions": {}}
    context = {"is_enterprise": True}

    resolved = resolve_conditions(policy, context)

    assert resolved == {}


def test_resolve_no_conditions_in_policy():
    """Return empty dict when no conditions in policy."""
    policy = {"policy_version": "1.0", "roles": ["planner"]}
    context = {"is_enterprise": True}

    resolved = resolve_conditions(policy, context)

    assert resolved == {}


def test_resolve_optional_condition_without_default():
    """Skip optional condition when not in context and no default."""
    policy = {
        "conditions": {
            "is_enterprise": {"type": "boolean"},  # Optional, no default
            "audit_enabled": {"type": "boolean", "default": True}
        }
    }
    context = {}

    resolved = resolve_conditions(policy, context)

    # is_enterprise is skipped, audit_enabled uses default
    assert resolved == {"audit_enabled": True}


def test_resolve_condition_false_value():
    """Resolve condition with explicit False value (not missing)."""
    policy = {
        "conditions": {
            "is_enterprise": {"type": "boolean", "required": True}
        }
    }
    context = {"is_enterprise": False}

    resolved = resolve_conditions(policy, context)

    assert resolved == {"is_enterprise": False}


def test_resolve_condition_non_boolean_default_raises_error():
    """Raise error when condition default is not boolean."""
    policy = {
        "conditions": {
            "is_enterprise": {"type": "boolean", "default": "false"}  # Wrong type
        }
    }
    context = {}

    with pytest.raises(ConditionResolutionError) as exc_info:
        resolve_conditions(policy, context)

    assert exc_info.value.code == "CONDITION_RESOLUTION_ERROR"
    assert exc_info.value.details["condition"] == "is_enterprise"
    assert exc_info.value.details["default_type"] == "str"
    assert "default must be boolean" in str(exc_info.value)
