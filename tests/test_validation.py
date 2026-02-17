import pytest
from src.validator import validate_preconditions
from src.errors import PreconditionError


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
