import datetime
from decimal import Decimal

import pytest

from aigc._internal.enforcement import enforce_invocation
from aigc._internal.errors import InvocationValidationError


def _valid_invocation():
    return {
        "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
        "model_provider": "openai",
        "model_identifier": "gpt-test-model",
        "role": "planner",
        "input": {"task": "describe system"},
        "output": {"result": "description", "confidence": 0.99},
        "context": {"role_declared": True, "schema_exists": True},
    }


@pytest.mark.parametrize("missing_key", ["policy_file", "role", "output", "context"])
def test_missing_required_key_raises_typed_error(missing_key):
    invocation = _valid_invocation()
    invocation.pop(missing_key)

    with pytest.raises(InvocationValidationError) as exc_info:
        enforce_invocation(invocation)

    assert exc_info.value.code == "INVOCATION_VALIDATION_ERROR"
    assert missing_key in exc_info.value.details["missing_fields"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("policy_file", ""),
        ("role", 42),
        ("model_provider", None),
        ("input", []),
        ("output", "bad"),
        ("context", "bad"),
    ],
)
def test_invalid_types_raise_typed_error(field, value):
    invocation = _valid_invocation()
    invocation[field] = value

    with pytest.raises(InvocationValidationError) as exc_info:
        enforce_invocation(invocation)

    assert exc_info.value.code == "INVOCATION_VALIDATION_ERROR"
    assert exc_info.value.details["field"] == field


def test_invocation_must_be_mapping():
    with pytest.raises(InvocationValidationError) as exc_info:
        enforce_invocation([])  # type: ignore[arg-type]
    assert exc_info.value.code == "INVOCATION_VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("context", {"timestamp": datetime.datetime.now()}),
        ("input", {"amount": Decimal("9.99")}),
        ("output", {"data": {1, 2, 3}}),
        ("context", {"nested": {"deep": datetime.date.today()}}),
    ],
)
def test_non_serializable_field_raises_at_entry(field, value):
    invocation = _valid_invocation()
    invocation[field] = value

    with pytest.raises(InvocationValidationError) as exc_info:
        enforce_invocation(invocation)

    assert exc_info.value.code == "INVOCATION_VALIDATION_ERROR"
    assert exc_info.value.details["field"] == field
    assert "not JSON-serializable" in str(exc_info.value)
