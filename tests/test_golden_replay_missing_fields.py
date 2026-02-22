"""
Test golden replay for invocation validation failure (missing required fields).

This test validates that invocations with missing required fields
raise InvocationValidationError (subclass of GovernanceViolationError).
"""

import json

import pytest

from src.enforcement import enforce_invocation
from src.errors import InvocationValidationError


def test_golden_replay_missing_fields():
    """
    Verify that invocations with missing required fields raise
    InvocationValidationError with the correct error code.
    """
    # Load golden replay
    with open(
        "tests/golden_replays/golden_invocation_missing_fields.json"
    ) as f:
        golden = json.load(f)

    invocation = golden["invocation"]
    expected_exception = golden["expected_exception"]
    expected_code = golden["expected_exception_code"]

    # Execute enforcement and capture exception
    with pytest.raises(InvocationValidationError) as exc_info:
        enforce_invocation(invocation)

    # Verify exception type and code
    assert exc_info.value.__class__.__name__ == expected_exception
    assert exc_info.value.code == expected_code
