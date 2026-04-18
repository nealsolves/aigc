"""PR-08 allowed_transitions enforcement tests."""
from __future__ import annotations
import pytest
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import WorkflowTransitionDeniedError, WorkflowRoleViolationError
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


def _session(transitions=None, allowed_roles=None):
    a = AIGC()
    s = GovernanceSession(a, str(uuid.uuid4()), POLICY, None)
    if transitions is not None:
        s._allowed_transitions = transitions
    if allowed_roles is not None:
        s._allowed_agent_roles = allowed_roles
    return s


def test_allowed_transition_passes():
    """A transition in the allowed map must succeed."""
    s = _session(transitions={"step-a": ["step-b"]})
    with s:
        t1 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-a")
        s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
        t2 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-b")
        s.enforce_step_post_call(t2, dict(_GOOD_OUTPUT))
        s.complete()
    assert s.workflow_artifact["status"] == "COMPLETED"


def test_disallowed_transition_raises():
    """A transition not in the map must raise WorkflowTransitionDeniedError."""
    s = _session(transitions={"step-a": ["step-b"]})
    with pytest.raises(WorkflowTransitionDeniedError):
        with s:
            t1 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-a")
            s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
            s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-c")  # not allowed


def test_first_step_no_transition_check():
    """First step always allowed (no prior step to transition from)."""
    s = _session(transitions={"step-a": ["step-b"]})
    with s:
        t1 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-a")
        s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
        s.complete()
    assert s.workflow_artifact["status"] == "COMPLETED"


def test_transition_not_declared_for_from_step_raises():
    """Missing from_step key in transitions map means no transitions allowed from that step."""
    # step-a is not in the map at all, so after completing step-a, any next step is denied
    s = _session(transitions={"step-x": ["step-y"]})
    with pytest.raises(WorkflowTransitionDeniedError):
        with s:
            t1 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-a")
            s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
            s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-b")


def test_no_transition_policy_no_enforcement():
    """Without allowed_transitions, steps may follow any order."""
    s = _session()  # no transitions
    with s:
        t1 = s.enforce_step_pre_call(dict(_BASE_INV))
        s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
        t2 = s.enforce_step_pre_call(dict(_BASE_INV))
        s.enforce_step_post_call(t2, dict(_GOOD_OUTPUT))
        s.complete()
    assert s.workflow_artifact["status"] == "COMPLETED"


def test_role_violation_raises():
    """Invocation role not in allowed_agent_roles must raise WorkflowRoleViolationError."""
    s = _session(allowed_roles=["analyst"])  # "planner" not allowed
    with pytest.raises(WorkflowRoleViolationError):
        with s:
            s.enforce_step_pre_call(dict(_BASE_INV))  # role="planner" not in ["analyst"]
