"""PR-08 participant enforcement tests."""
from __future__ import annotations
import pytest
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import WorkflowParticipantMismatchError
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


def _session(participants):
    a = AIGC()
    s = GovernanceSession(a, str(uuid.uuid4()), POLICY, None)
    s._participants = participants
    s._participants_by_id = {p["id"]: p for p in participants}
    return s


def test_declared_participant_id_required():
    """When participants declared, missing participant_id raises WorkflowParticipantMismatchError."""
    s = _session([{"id": "agent-1"}])
    with pytest.raises(WorkflowParticipantMismatchError) as exc_info:
        with s:
            s.enforce_step_pre_call(dict(_BASE_INV))  # no participant_id
    assert exc_info.value.details.get("reason_code") == "WORKFLOW_PARTICIPANT_ID_REQUIRED"


def test_unknown_participant_rejected():
    """participant_id not in declared list raises WorkflowParticipantMismatchError."""
    s = _session([{"id": "agent-1"}])
    with pytest.raises(WorkflowParticipantMismatchError):
        with s:
            s.enforce_step_pre_call(dict(_BASE_INV), participant_id="unknown-agent")


def test_participant_role_mismatch_rejected():
    """Invocation role not in participant's roles raises WorkflowParticipantMismatchError."""
    s = _session([{"id": "agent-1", "roles": ["analyst"]}])
    with pytest.raises(WorkflowParticipantMismatchError) as exc_info:
        with s:
            # _BASE_INV has role="planner", participant only allows "analyst"
            s.enforce_step_pre_call(dict(_BASE_INV), participant_id="agent-1")
    assert exc_info.value.details.get("reason_code") == "WORKFLOW_PARTICIPANT_ROLE_MISMATCH"


def test_no_participant_policy_keeps_participant_optional():
    """Without participants, participant_id is optional and not validated."""
    a = AIGC()
    s = GovernanceSession(a, str(uuid.uuid4()), POLICY, None)
    with s:
        t = s.enforce_step_pre_call(dict(_BASE_INV))  # no participant_id, no validation
        s.enforce_step_post_call(t, dict(_GOOD_OUTPUT))
        s.complete()
    assert s.workflow_artifact["status"] == "COMPLETED"
