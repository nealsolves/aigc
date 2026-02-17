"""
Golden Trace Success Test

This test ensures that a canonical “good” invocation succeeds
and produces an audit artifact that matches expectations.
"""

import json
from src.enforcement import enforce_invocation

GOLDEN_SUCCESS = "tests/golden_traces/golden_invocation_success.json"
EXPECTED_AUDIT = "tests/golden_traces/golden_expected_audit.json"

def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def test_golden_trace_success():
    """
    Enforce governance on a known-good invocation and compare
    the audit artifact to the expected golden artifact.
    """
    invocation = load_json(GOLDEN_SUCCESS)

    audit = enforce_invocation(invocation)

    # Load expected artifact
    expected = load_json(EXPECTED_AUDIT)

    # Validate stable fields
    assert audit["model_provider"] == expected["model_provider"]
    assert audit["model_identifier"] == expected["model_identifier"]
    assert audit["role"] == expected["role"]
    assert audit["policy_version"] == expected["policy_version"]
    assert audit["audit_schema_version"] == expected["audit_schema_version"]
    assert audit["enforcement_result"] == expected["enforcement_result"]
    assert audit["policy_file"] == expected["policy_file"]
    assert audit["policy_schema_version"] == expected["policy_schema_version"]
    assert audit["failures"] == []
    assert audit["metadata"]["preconditions_satisfied"] == [
        "role_declared",
        "schema_exists",
    ]
    assert audit["metadata"]["postconditions_satisfied"] == [
        "output_schema_valid",
    ]
    assert audit["metadata"]["schema_validation"] == "passed"
