import warnings

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


# --- Typed precondition tests (D-01) ---

def test_typed_precondition_string_passes():
    policy = {"pre_conditions": {"required": {
        "session_id": {"type": "string"}
    }}}
    satisfied = validate_preconditions({"session_id": "abc-123"}, policy)
    assert "session_id" in satisfied


def test_typed_precondition_string_fails_on_bool():
    """Passing True for a typed string precondition must fail."""
    policy = {"pre_conditions": {"required": {
        "session_id": {"type": "string"}
    }}}
    with pytest.raises(PreconditionError) as exc_info:
        validate_preconditions({"session_id": True}, policy)
    assert "session_id" in str(exc_info.value)


def test_typed_precondition_pattern_passes():
    policy = {"pre_conditions": {"required": {
        "uuid": {"type": "string", "pattern": "^[a-f0-9-]{36}$"}
    }}}
    satisfied = validate_preconditions(
        {"uuid": "550e8400-e29b-41d4-a716-446655440000"}, policy
    )
    assert "uuid" in satisfied


def test_typed_precondition_pattern_fails():
    policy = {"pre_conditions": {"required": {
        "uuid": {"type": "string", "pattern": "^[a-f0-9-]{36}$"}
    }}}
    with pytest.raises(PreconditionError):
        validate_preconditions({"uuid": "not-a-uuid"}, policy)


def test_typed_precondition_integer_passes():
    policy = {"pre_conditions": {"required": {
        "count": {"type": "integer", "minimum": 1}
    }}}
    satisfied = validate_preconditions({"count": 5}, policy)
    assert "count" in satisfied


def test_typed_precondition_integer_fails_below_minimum():
    policy = {"pre_conditions": {"required": {
        "count": {"type": "integer", "minimum": 1}
    }}}
    with pytest.raises(PreconditionError):
        validate_preconditions({"count": 0}, policy)


def test_typed_precondition_enum_passes():
    policy = {"pre_conditions": {"required": {
        "env": {"type": "string", "enum": ["prod", "staging", "dev"]}
    }}}
    satisfied = validate_preconditions({"env": "prod"}, policy)
    assert "env" in satisfied


def test_typed_precondition_enum_fails():
    policy = {"pre_conditions": {"required": {
        "env": {"type": "string", "enum": ["prod", "staging"]}
    }}}
    with pytest.raises(PreconditionError):
        validate_preconditions({"env": "test"}, policy)


def test_typed_precondition_missing_key():
    policy = {"pre_conditions": {"required": {
        "session_id": {"type": "string"}
    }}}
    with pytest.raises(PreconditionError) as exc_info:
        validate_preconditions({}, policy)
    assert "session_id" in str(exc_info.value)


def test_typed_precondition_type_any_acts_as_legacy():
    """type: any behaves like legacy key-existence check."""
    policy = {"pre_conditions": {"required": {
        "flag": {"type": "any"}
    }}}
    satisfied = validate_preconditions({"flag": True}, policy)
    assert "flag" in satisfied


def test_typed_precondition_deterministic_ordering():
    """Typed preconditions validated in sorted key order."""
    policy = {"pre_conditions": {"required": {
        "z_key": {"type": "string"},
        "a_key": {"type": "string"},
    }}}
    satisfied = validate_preconditions(
        {"a_key": "val", "z_key": "val"}, policy
    )
    assert satisfied == ["a_key", "z_key"]


def test_bare_string_precondition_emits_deprecation_warning():
    policy = {"pre_conditions": {"required": ["role_declared"]}}
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        validate_preconditions({"role_declared": True}, policy)
    assert any(issubclass(warning.category, DeprecationWarning) for warning in w)
