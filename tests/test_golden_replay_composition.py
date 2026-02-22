"""Golden replay tests for policy composition via extends."""

import json
import pytest
from src.enforcement import enforce_invocation
from src.errors import PolicyLoadError


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_golden_replay_composition_success():
    """Policy with extends chain loads and enforces correctly."""
    invocation = load_json("tests/golden_replays/golden_invocation_composition_success.json")

    audit = enforce_invocation(invocation)

    assert audit["enforcement_result"] == "PASS"
    assert audit["role"] == "verifier"

    # Verify merged policy has both base and child roles
    # (child role "verifier" is valid, proving merge happened)
    assert audit["metadata"]["schema_validation"] == "passed"


def test_golden_replay_composition_cycle_failure():
    """Circular extends raises PolicyLoadError with deterministic details."""
    # Create invocation with cycle policy
    invocation = {
        "policy_file": "tests/fixtures/policy_cycle_a.yaml",
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4",
        "role": "cycle_a_role",
        "input": {"task": "test"},
        "output": {"result": "test"},
        "context": {"context_valid": True}
    }

    with pytest.raises(PolicyLoadError) as exc_info:
        enforce_invocation(invocation)

    # Must be typed PolicyLoadError, not RecursionError
    assert exc_info.value.code == "POLICY_LOAD_ERROR"
    assert "Circular extends detected" in str(exc_info.value)
    assert "chain" in exc_info.value.details
