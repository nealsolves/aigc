"""
PR-08 budget accounting tests: max_steps and max_total_tool_calls enforcement.
"""
from __future__ import annotations
import pytest
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import (
    WorkflowStepBudgetExceededError,
    WorkflowToolBudgetExceededError,
    SessionStateError,
)

BUDGET_POLICY = "tests/test_policies/workflow_budget_policy.yaml"

_BASE_INV = {
    "policy_file": BUDGET_POLICY,
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "planner",
    "input": {"query": "test"},
    "context": {"role_declared": True, "schema_exists": True},
}

_GOOD_OUTPUT = {"result": "answer"}


def _aigc() -> AIGC:
    return AIGC()


# ---------------------------------------------------------------------------
# max_steps enforcement
# ---------------------------------------------------------------------------

def test_steps_within_budget_succeed():
    """2 steps with max_steps=2 must succeed."""
    a = _aigc()
    with a.open_session(policy_file=BUDGET_POLICY) as session:
        for _ in range(2):
            token = session.enforce_step_pre_call(dict(_BASE_INV))
            session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
        session.complete()
    assert session.workflow_artifact["status"] == "COMPLETED"


def test_step_beyond_max_steps_raises():
    """Step 3 with max_steps=2 must raise WorkflowStepBudgetExceededError."""
    a = _aigc()
    with pytest.raises(WorkflowStepBudgetExceededError) as exc_info:
        with a.open_session(policy_file=BUDGET_POLICY) as session:
            for _ in range(2):
                token = session.enforce_step_pre_call(dict(_BASE_INV))
                session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
            # This 3rd step must raise
            session.enforce_step_pre_call(dict(_BASE_INV))
    assert exc_info.value.code == "WORKFLOW_STEP_BUDGET_EXCEEDED"


def test_step_beyond_max_steps_includes_session_id_in_details():
    """Budget error details must include session_id for doctor diagnostics."""
    a = _aigc()
    with pytest.raises(WorkflowStepBudgetExceededError) as exc_info:
        with a.open_session(policy_file=BUDGET_POLICY) as session:
            for _ in range(2):
                t = session.enforce_step_pre_call(dict(_BASE_INV))
                session.enforce_step_post_call(t, dict(_GOOD_OUTPUT))
            session.enforce_step_pre_call(dict(_BASE_INV))
    assert "session_id" in exc_info.value.details
    assert "max_steps" in exc_info.value.details


def test_unlimited_budget_when_no_session_policy():
    """Session with no policy_file has no step budget cap."""
    POLICY = "tests/golden_replays/golden_policy_v1.yaml"
    a = _aigc()
    inv = dict(_BASE_INV)
    inv["policy_file"] = POLICY
    with a.open_session() as session:  # no session-level policy_file
        for _ in range(5):
            token = session.enforce_step_pre_call(dict(inv))
            session.enforce_step_post_call(token, {"result": "answer", "confidence": 0.95})
        session.complete()
    assert session.workflow_artifact["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# max_total_tool_calls enforcement
# ---------------------------------------------------------------------------

def test_tool_calls_within_budget_succeed():
    """3 tool_calls total with max_total_tool_calls=3 must succeed."""
    a = _aigc()
    inv_with_tools = dict(_BASE_INV)
    inv_with_tools["tool_calls"] = [
        {"name": "search", "arguments": {}},
        {"name": "analyze", "arguments": {}},
    ]
    with a.open_session(policy_file=BUDGET_POLICY) as session:
        # Step 1: 2 tool calls
        token = session.enforce_step_pre_call(dict(inv_with_tools))
        session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
        # Step 2: 1 tool call
        inv_one = dict(_BASE_INV)
        inv_one["tool_calls"] = [{"name": "search", "arguments": {}}]
        token2 = session.enforce_step_pre_call(dict(inv_one))
        session.enforce_step_post_call(token2, dict(_GOOD_OUTPUT))
        session.complete()
    assert session.workflow_artifact["status"] == "COMPLETED"


def test_tool_calls_exceed_budget_raises():
    """Projecting beyond max_total_tool_calls=3 must raise WorkflowToolBudgetExceededError."""
    a = _aigc()
    inv_with_tools = dict(_BASE_INV)
    inv_with_tools["tool_calls"] = [
        {"name": "search", "arguments": {}},
        {"name": "analyze", "arguments": {}},
        {"name": "write", "arguments": {}},
        {"name": "review", "arguments": {}},
    ]
    with pytest.raises(WorkflowToolBudgetExceededError) as exc_info:
        with a.open_session(policy_file=BUDGET_POLICY) as session:
            session.enforce_step_pre_call(dict(inv_with_tools))
    assert exc_info.value.code == "WORKFLOW_TOOL_BUDGET_EXCEEDED"


def test_tool_call_budget_check_happens_at_pre_call():
    """Tool-call budget check fires at enforce_step_pre_call, not post_call."""
    a = _aigc()
    # Step 1: 2 tool calls
    inv_two = dict(_BASE_INV)
    inv_two["tool_calls"] = [
        {"name": "search", "arguments": {}},
        {"name": "analyze", "arguments": {}},
    ]
    # Step 2: 2 more tool calls → would push total to 4, exceeding 3
    inv_two_more = dict(_BASE_INV)
    inv_two_more["tool_calls"] = [
        {"name": "write", "arguments": {}},
        {"name": "review", "arguments": {}},
    ]
    with pytest.raises(WorkflowToolBudgetExceededError):
        with a.open_session(policy_file=BUDGET_POLICY) as session:
            token = session.enforce_step_pre_call(dict(inv_two))
            session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
            # This pre_call must raise — projected total would be 4 > 3
            session.enforce_step_pre_call(dict(inv_two_more))
