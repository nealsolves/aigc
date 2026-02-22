"""Golden replay tests for named condition resolution."""

import json
import pytest
from src.enforcement import enforce_invocation
from src.errors import ConditionResolutionError


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_golden_replay_conditions_success():
    """All conditions resolved correctly (context + defaults)."""
    invocation = load_json("tests/golden_replays/golden_invocation_conditions_success.json")

    audit = enforce_invocation(invocation)

    assert audit["enforcement_result"] == "PASS"
    assert audit["role"] == "planner"

    # Verify conditions were resolved
    conditions_resolved = audit["metadata"]["conditions_resolved"]
    assert conditions_resolved["is_enterprise"] is True  # from context
    assert conditions_resolved["audit_enabled"] is True  # from context (required)
    assert conditions_resolved["premium_features"] is False  # from context

    # Verify schema validation passed
    assert audit["metadata"]["schema_validation"] == "passed"


def test_golden_replay_conditions_missing_required():
    """Missing required condition raises ConditionResolutionError."""
    invocation = load_json("tests/golden_replays/golden_invocation_conditions_missing_required.json")

    with pytest.raises(ConditionResolutionError) as exc_info:
        enforce_invocation(invocation)

    assert exc_info.value.code == "CONDITION_RESOLUTION_ERROR"
    assert "audit_enabled" in str(exc_info.value)
    assert "required" in str(exc_info.value).lower()


def test_golden_replay_conditions_wrong_type():
    """Condition value with wrong type raises ConditionResolutionError."""
    invocation = load_json("tests/golden_replays/golden_invocation_conditions_wrong_type.json")

    with pytest.raises(ConditionResolutionError) as exc_info:
        enforce_invocation(invocation)

    assert exc_info.value.code == "CONDITION_RESOLUTION_ERROR"
    assert "is_enterprise" in str(exc_info.value)
    assert "boolean" in str(exc_info.value).lower()
