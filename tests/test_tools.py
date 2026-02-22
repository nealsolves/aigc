"""Tests for tool constraint validation."""

import pytest
from aigc._internal.tools import validate_tool_constraints
from aigc._internal.errors import ToolConstraintViolationError


def test_tool_within_limits_passes():
    """Tool calls within max_calls limit pass validation."""
    policy = {
        "tools": {
            "allowed_tools": [
                {"name": "search", "max_calls": 3}
            ]
        }
    }
    invocation = {
        "tool_calls": [
            {"name": "search", "call_id": "tc-1"},
            {"name": "search", "call_id": "tc-2"}
        ]
    }

    result = validate_tool_constraints(invocation, policy)

    assert result["tools_checked"] == ["search"]
    assert result["violations"] == []


def test_tool_exceeds_max_calls_fails():
    """Tool exceeding max_calls raises error."""
    policy = {
        "tools": {
            "allowed_tools": [
                {"name": "search", "max_calls": 2}
            ]
        }
    }
    invocation = {
        "tool_calls": [
            {"name": "search", "call_id": "tc-1"},
            {"name": "search", "call_id": "tc-2"},
            {"name": "search", "call_id": "tc-3"}  # Exceeds max
        ]
    }

    with pytest.raises(ToolConstraintViolationError) as exc_info:
        validate_tool_constraints(invocation, policy)

    assert exc_info.value.code == "TOOL_CONSTRAINT_VIOLATION"
    assert exc_info.value.details["tool"] == "search"
    assert exc_info.value.details["actual_calls"] == 3
    assert exc_info.value.details["max_calls"] == 2


def test_tool_not_in_allowlist_fails():
    """Tool not in allowed_tools raises error."""
    policy = {
        "tools": {
            "allowed_tools": [
                {"name": "search", "max_calls": 5}
            ]
        }
    }
    invocation = {
        "tool_calls": [
            {"name": "unauthorized_tool", "call_id": "tc-1"}
        ]
    }

    with pytest.raises(ToolConstraintViolationError) as exc_info:
        validate_tool_constraints(invocation, policy)

    assert exc_info.value.code == "TOOL_CONSTRAINT_VIOLATION"
    assert exc_info.value.details["tool"] == "unauthorized_tool"
    assert "search" in exc_info.value.details["allowed_tools"]


def test_multiple_tools_all_valid():
    """Multiple tools all within limits pass validation."""
    policy = {
        "tools": {
            "allowed_tools": [
                {"name": "search", "max_calls": 3},
                {"name": "analyze", "max_calls": 2}
            ]
        }
    }
    invocation = {
        "tool_calls": [
            {"name": "search", "call_id": "tc-1"},
            {"name": "search", "call_id": "tc-2"},
            {"name": "analyze", "call_id": "tc-3"}
        ]
    }

    result = validate_tool_constraints(invocation, policy)

    assert set(result["tools_checked"]) == {"search", "analyze"}
    assert result["violations"] == []


def test_no_tools_in_policy_skips_validation():
    """No tools block in policy skips validation."""
    policy = {"policy_version": "1.0", "roles": ["planner"]}
    invocation = {
        "tool_calls": [
            {"name": "search", "call_id": "tc-1"}
        ]
    }

    result = validate_tool_constraints(invocation, policy)

    assert result["tools_checked"] == []
    assert result["violations"] == []


def test_no_tool_calls_in_invocation_skips_validation():
    """No tool_calls in invocation skips validation."""
    policy = {
        "tools": {
            "allowed_tools": [
                {"name": "search", "max_calls": 3}
            ]
        }
    }
    invocation = {}  # No tool_calls

    result = validate_tool_constraints(invocation, policy)

    assert result["tools_checked"] == []
    assert result["violations"] == []


def test_exact_max_calls_allowed():
    """Calling exactly max_calls is allowed."""
    policy = {
        "tools": {
            "allowed_tools": [
                {"name": "search", "max_calls": 2}
            ]
        }
    }
    invocation = {
        "tool_calls": [
            {"name": "search", "call_id": "tc-1"},
            {"name": "search", "call_id": "tc-2"}
        ]
    }

    result = validate_tool_constraints(invocation, policy)

    assert result["tools_checked"] == ["search"]
    assert result["violations"] == []


def test_tools_checked_sorted():
    """Tools checked are returned in sorted order."""
    policy = {
        "tools": {
            "allowed_tools": [
                {"name": "search", "max_calls": 5},
                {"name": "analyze", "max_calls": 5},
                {"name": "verify", "max_calls": 5}
            ]
        }
    }
    invocation = {
        "tool_calls": [
            {"name": "verify", "call_id": "tc-1"},
            {"name": "analyze", "call_id": "tc-2"},
            {"name": "search", "call_id": "tc-3"}
        ]
    }

    result = validate_tool_constraints(invocation, policy)

    assert result["tools_checked"] == ["analyze", "search", "verify"]  # Sorted
