"""PR-08 escalation enforcement tests."""
from __future__ import annotations
import pytest
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import WorkflowApprovalRequiredError
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


def _session(escalation):
    a = AIGC()
    s = GovernanceSession(a, str(uuid.uuid4()), POLICY, None)
    s._escalation = escalation
    return s


def test_escalation_after_n_steps_auto_pauses_and_raises():
    """After N authorized steps, escalation pauses session and raises ApprovalRequired."""
    s = _session({"require_approval_after_steps": 2})
    with pytest.raises(WorkflowApprovalRequiredError):
        with s:
            t1 = s.enforce_step_pre_call(dict(_BASE_INV))
            s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
            t2 = s.enforce_step_pre_call(dict(_BASE_INV))
            s.enforce_step_post_call(t2, dict(_GOOD_OUTPUT))
            # Now authorized_step_count==2, 2 % 2 == 0 and > 0 → triggers
            s.enforce_step_pre_call(dict(_BASE_INV))


def test_escalation_for_role_auto_pauses_and_raises():
    """Invocation with role in require_approval_for_roles triggers approval."""
    s = _session({"require_approval_for_roles": ["planner"]})
    with pytest.raises(WorkflowApprovalRequiredError):
        with s:
            s.enforce_step_pre_call(dict(_BASE_INV))  # role=planner triggers it


def test_escalation_records_checkpoint_before_exception():
    """Escalation must record an approval checkpoint before raising."""
    s = _session({"require_approval_after_steps": 1})
    with pytest.raises(WorkflowApprovalRequiredError):
        with s:
            t1 = s.enforce_step_pre_call(dict(_BASE_INV))
            s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
            s.enforce_step_pre_call(dict(_BASE_INV))  # triggers at count=1
    artifact = s.workflow_artifact
    checkpoints = artifact.get("approval_checkpoints", [])
    assert len(checkpoints) >= 1
    assert checkpoints[-1]["status"] == "pending"


def test_host_can_resume_after_escalation_requirement():
    """After escalation raises, the exception carries a checkpoint_id in its details."""
    s = _session({"require_approval_for_roles": ["planner"]})
    caught_approval_id = None
    try:
        with s:
            s.enforce_step_pre_call(dict(_BASE_INV))
    except WorkflowApprovalRequiredError as exc:
        caught_approval_id = exc.details.get("checkpoint_id")

    # The approval checkpoint was created before the raise
    assert caught_approval_id is not None
