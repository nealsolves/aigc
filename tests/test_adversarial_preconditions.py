"""Adversarial precondition bypass tests (WS-17).

Verifies that typed preconditions reject values that would
pass bare-string truthiness checks but violate type contracts.
"""

import pytest

from aigc._internal.errors import PreconditionError
from aigc._internal.validator import _validate_typed_precondition


def test_boolean_true_rejected_for_string_type():
    """True (bool) must not satisfy a string-typed precondition."""
    with pytest.raises(PreconditionError):
        _validate_typed_precondition(
            "key", {"type": "string"}, {"key": True}
        )


def test_empty_string_rejected_for_minlength():
    """Empty string must not satisfy a minLength constraint."""
    with pytest.raises(PreconditionError):
        _validate_typed_precondition(
            "key", {"type": "string", "minLength": 1}, {"key": ""}
        )


def test_zero_rejected_for_minimum():
    """Zero must not satisfy a minimum > 0 constraint."""
    with pytest.raises(PreconditionError):
        _validate_typed_precondition(
            "key", {"type": "integer", "minimum": 1}, {"key": 0}
        )


def test_none_rejected_for_any_type():
    """None must not satisfy a string-typed precondition."""
    with pytest.raises(PreconditionError):
        _validate_typed_precondition(
            "key", {"type": "string"}, {"key": None}
        )


def test_missing_key_rejected():
    """Missing context key must raise PreconditionError."""
    with pytest.raises(PreconditionError, match="Missing"):
        _validate_typed_precondition(
            "key", {"type": "string"}, {}
        )


def test_wrong_enum_value_rejected():
    """Value not in enum must be rejected."""
    with pytest.raises(PreconditionError):
        _validate_typed_precondition(
            "key", {"enum": ["a", "b", "c"]}, {"key": "d"}
        )
