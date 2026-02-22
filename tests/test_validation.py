import pytest
from aigc._internal.validator import validate_preconditions, validate_postconditions
from aigc._internal.errors import GovernanceViolationError, PreconditionError


def test_precondition_missing():
    with pytest.raises(PreconditionError) as exc_info:
        validate_preconditions({}, {"pre_conditions": {"required": ["role_declared"]}})
    assert exc_info.value.code == "PRECONDITION_FAILED"
    assert exc_info.value.details["precondition"] == "role_declared"


def test_precondition_false():
    with pytest.raises(PreconditionError):
        validate_preconditions(
            {"role_declared": False},
            {"pre_conditions": {"required": ["role_declared"]}},
        )


def test_precondition_success_returns_satisfied():
    satisfied = validate_preconditions(
        {"role_declared": True, "schema_exists": True},
        {"pre_conditions": {"required": ["role_declared", "schema_exists"]}},
    )
    assert satisfied == ["role_declared", "schema_exists"]


def test_postcondition_unsupported_name_raises():
    """validate_postconditions raises on an unknown postcondition name (line 98)."""
    policy = {"post_conditions": {"required": ["nonexistent_check"]}}
    with pytest.raises(GovernanceViolationError) as exc_info:
        validate_postconditions(policy, schema_valid=True)
    assert exc_info.value.code == "UNSUPPORTED_POSTCONDITION"
    assert "nonexistent_check" in str(exc_info.value)
