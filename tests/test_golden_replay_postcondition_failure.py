"""
Test golden replay for postcondition validation failure with audit artifact emission.

This test validates that postcondition failures emit FAIL audit artifacts
with the expected stable fields.
"""

import json

import pytest

from aigc._internal.enforcement import enforce_invocation
from aigc._internal.errors import GovernanceViolationError


def test_golden_replay_postcondition_failure():
    """
    Verify that postcondition validation failures emit FAIL audit artifacts
    matching the golden replay stable fields.
    """
    # Load golden replay
    with open(
        "tests/golden_replays/golden_invocation_postcondition_failure.json"
    ) as f:
        golden = json.load(f)

    invocation = golden["invocation"]
    expected_exception = golden["expected_exception"]
    expected_code = golden["expected_exception_code"]
    expected_stable_fields = golden["expected_audit_artifact_stable_fields"]

    # Execute enforcement and capture exception
    with pytest.raises(GovernanceViolationError) as exc_info:
        enforce_invocation(invocation)

    # Verify exception type and code
    assert exc_info.value.__class__.__name__ == expected_exception
    assert exc_info.value.code == expected_code

    # Verify audit artifact is attached to exception
    assert hasattr(exc_info.value, "audit_artifact")
    audit = exc_info.value.audit_artifact

    # Verify stable fields match golden replay expectations
    for field, expected_value in expected_stable_fields.items():
        assert (
            audit[field] == expected_value
        ), f"Audit field '{field}' mismatch: expected {expected_value}, got {audit[field]}"

    # Verify required audit fields are present (even if volatile)
    required_fields = [
        "audit_schema_version",
        "policy_file",
        "policy_schema_version",
        "policy_version",
        "model_provider",
        "model_identifier",
        "role",
        "enforcement_result",
        "failures",
        "failure_gate",
        "failure_reason",
        "input_checksum",
        "output_checksum",
        "timestamp",
        "metadata",
    ]

    for field in required_fields:
        assert field in audit, f"Required audit field '{field}' missing"

    # Verify failure_reason is not null for FAIL results
    assert audit["failure_reason"] is not None
    assert isinstance(audit["failure_reason"], str)
    assert len(audit["failure_reason"]) > 0
