"""
Golden Replay Failure Test

Ensures that a canonical “bad” invocation fails governance enforcement.
"""

import json
import pytest
from aigc._internal.enforcement import enforce_invocation
from aigc._internal.errors import SchemaValidationError

GOLDEN_FAILURE = "tests/golden_replays/golden_invocation_failure.json"

def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def test_golden_replay_failure():
    """
    Attempting to enforce governance on a known-bad invocation
    should raise a schema validation error.
    """
    invocation = load_json(GOLDEN_FAILURE)

    with pytest.raises(SchemaValidationError) as exc_info:
        enforce_invocation(invocation)
    assert exc_info.value.code == "OUTPUT_SCHEMA_VALIDATION_ERROR"
