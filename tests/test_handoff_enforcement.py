"""PR-08 handoffs enforcement tests."""
from __future__ import annotations
import pytest
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import WorkflowHandoffDeniedError
from aigc._internal.session import GovernanceSession
import uuid

POLICY = "tests/golden_replays/golden_policy_v1.yaml"
_BASE_INV = {
    "policy_file": POLICY, "model_provider": "openai",
    "model_identifier": "gpt-4", "role": "planner",
    "input": {"query": "test"},
    "context": {"role_declared": True, "schema_exists": True},
}
_GOOD_OUTPUT = {"result": "answer", "confidence": 0.95}


def _session(handoffs):
    a = AIGC()
    s = GovernanceSession(a, str(uuid.uuid4()), POLICY, None)
    s._handoffs = handoffs
    return s


def test_allowed_handoff_passes():
    """Allowed handoff pair must succeed."""
    s = _session([{"from": "agent-1", "to": "agent-2"}])
    with s:
        t1 = s.enforce_step_pre_call(dict(_BASE_INV), participant_id="agent-1")
        s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
        t2 = s.enforce_step_pre_call(dict(_BASE_INV), participant_id="agent-2")
        s.enforce_step_post_call(t2, dict(_GOOD_OUTPUT))
        s.complete()
    assert s.workflow_artifact["status"] == "COMPLETED"


def test_disallowed_handoff_raises():
    """Handoff pair not in declared list raises WorkflowHandoffDeniedError."""
    s = _session([{"from": "agent-1", "to": "agent-2"}])
    with pytest.raises(WorkflowHandoffDeniedError):
        with s:
            t1 = s.enforce_step_pre_call(dict(_BASE_INV), participant_id="agent-1")
            s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
            s.enforce_step_pre_call(dict(_BASE_INV), participant_id="agent-3")  # not allowed


def test_same_participant_no_handoff_check():
    """Same participant continuing its own steps skips handoff check."""
    s = _session([{"from": "agent-1", "to": "agent-2"}])
    with s:
        t1 = s.enforce_step_pre_call(dict(_BASE_INV), participant_id="agent-1")
        s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
        t2 = s.enforce_step_pre_call(dict(_BASE_INV), participant_id="agent-1")  # same
        s.enforce_step_post_call(t2, dict(_GOOD_OUTPUT))
        s.complete()
    assert s.workflow_artifact["status"] == "COMPLETED"


def test_null_participant_no_handoff_check():
    """Steps with no participant_id skip handoff check."""
    s = _session([{"from": "agent-1", "to": "agent-2"}])
    with s:
        t1 = s.enforce_step_pre_call(dict(_BASE_INV))  # no participant_id
        s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
        t2 = s.enforce_step_pre_call(dict(_BASE_INV))  # no participant_id
        s.enforce_step_post_call(t2, dict(_GOOD_OUTPUT))
        s.complete()
    assert s.workflow_artifact["status"] == "COMPLETED"


def test_handoffs_not_declared_no_enforcement():
    """Without handoffs policy, any participant sequence is allowed."""
    a = AIGC()
    s = GovernanceSession(a, str(uuid.uuid4()), POLICY, None)
    with s:
        t1 = s.enforce_step_pre_call(dict(_BASE_INV), participant_id="any-agent")
        s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
        t2 = s.enforce_step_pre_call(dict(_BASE_INV), participant_id="other-agent")
        s.enforce_step_post_call(t2, dict(_GOOD_OUTPUT))
        s.complete()
    assert s.workflow_artifact["status"] == "COMPLETED"
