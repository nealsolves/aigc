"""
Golden Trace Failure Test

Ensures that a canonical “bad” invocation fails governance enforcement.
"""

import json
import pytest
from src.enforcement import enforce_invocation
from src.errors import SchemaValidationError

GOLDEN_FAILURE = "tests/golden_traces/golden_invocation_failure.json"

def load_json(p):
    with open(p, "r") as f:
        return json.load(f)

def test_golden_trace_failure():
    """
    Attempting to enforce governance on a known-bad invocation
    should raise a schema validation error.
    """
    invocation = load_json(GOLDEN_FAILURE)

    with pytest.raises(SchemaValidationError):
        enforce_invocation(invocation)
