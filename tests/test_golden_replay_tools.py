"""Golden replay tests for tool constraint validation."""

import json
import pytest
from src.enforcement import enforce_invocation
from src.errors import ToolConstraintViolationError


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_golden_replay_tools_success():
    """Tool calls within limits pass validation."""
    invocation = load_json("tests/golden_replays/golden_invocation_tools_success.json")

    audit = enforce_invocation(invocation)

    assert audit["enforcement_result"] == "PASS"
    assert audit["metadata"]["tool_constraints"]["tools_checked"] == [
        "search_knowledge_base"
    ]
    assert audit["metadata"]["tool_constraints"]["violations"] == []


def test_golden_replay_tools_exceed_max():
    """Tool exceeding max_calls raises error and emits FAIL audit."""
    golden = load_json("tests/golden_replays/golden_invocation_tools_exceed_max.json")
    invocation = golden["invocation"]

    with pytest.raises(ToolConstraintViolationError) as exc_info:
        enforce_invocation(invocation)

    assert exc_info.value.code == golden["expected_exception_code"]
    assert exc_info.value.details["tool"] == "search_knowledge_base"
    assert exc_info.value.details["actual_calls"] == 3
    assert exc_info.value.details["max_calls"] == 2

    # Verify FAIL audit attached
    assert hasattr(exc_info.value, "audit_artifact")
    audit = exc_info.value.audit_artifact
    assert audit["enforcement_result"] == "FAIL"
    assert audit["failure_gate"] == "tool_validation"


def test_golden_replay_tools_not_allowed():
    """Unauthorized tool raises error and emits FAIL audit."""
    golden = load_json("tests/golden_replays/golden_invocation_tools_not_allowed.json")
    invocation = golden["invocation"]

    with pytest.raises(ToolConstraintViolationError) as exc_info:
        enforce_invocation(invocation)

    assert exc_info.value.code == golden["expected_exception_code"]
    assert exc_info.value.details["tool"] == "unauthorized_tool"

    # Verify FAIL audit attached
    assert hasattr(exc_info.value, "audit_artifact")
    audit = exc_info.value.audit_artifact
    assert audit["enforcement_result"] == "FAIL"
    assert audit["failure_gate"] == "tool_validation"
