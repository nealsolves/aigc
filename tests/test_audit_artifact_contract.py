"""
Audit Artifact Contract Test

This test ensures that the audit artifact always contains
required fields in accordance with the AIGC spec.
"""

import json
from src.audit import generate_audit_artifact

GOLDEN_SUCCESS = "tests/golden_traces/golden_invocation_success.json"

def load_json(p):
    with open(p, "r") as f:
        return json.load(f)

def test_audit_contract():
    """
    Ensure audit artifacts contain all required fields.
    """
    invocation = load_json(GOLDEN_SUCCESS)
    audit = generate_audit_artifact(invocation, {"policy_version": "1.0"})

    # Required fields
    assert "model_provider" in audit
    assert "model_identifier" in audit
    assert "role" in audit
    assert "policy_version" in audit
    assert "input_checksum" in audit
    assert "output_checksum" in audit
    assert "timestamp" in audit
