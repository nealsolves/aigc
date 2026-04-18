"""PR-08 required_sequence enforcement tests."""
from __future__ import annotations
import pytest
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import WorkflowSequenceViolationError
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


def _session(sequence):
    a = AIGC()
    s = GovernanceSession(a, str(uuid.uuid4()), POLICY, None)
    s._required_sequence = sequence
    return s


def test_required_sequence_in_order_passes():
    """Steps executed in sequence order must succeed."""
    s = _session(["step-a", "step-b", "step-c"])
    with s:
        t1 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-a")
        s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
        t2 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-b")
        s.enforce_step_post_call(t2, dict(_GOOD_OUTPUT))
        t3 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-c")
        s.enforce_step_post_call(t3, dict(_GOOD_OUTPUT))
        s.complete()
    assert s.workflow_artifact["status"] == "COMPLETED"


def test_required_sequence_out_of_order_raises():
    """Wrong step_id at sequence position raises WorkflowSequenceViolationError."""
    s = _session(["step-a", "step-b"])
    with pytest.raises(WorkflowSequenceViolationError):
        with s:
            t1 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-a")
            s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
            s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-WRONG")


def test_required_sequence_missing_step_id_raises():
    """Omitting step_id when sequence is declared raises WorkflowSequenceViolationError."""
    s = _session(["step-a"])
    with pytest.raises(WorkflowSequenceViolationError) as exc_info:
        with s:
            s.enforce_step_pre_call(dict(_BASE_INV))  # no step_id
    assert exc_info.value.details.get("reason_code") == "WORKFLOW_SEQUENCE_STEP_ID_REQUIRED"


def test_required_sequence_partial_completion_tracked():
    """After completing step-a, _sequence_position is 1."""
    s = _session(["step-a", "step-b"])
    with s:
        t1 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-a")
        s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
        assert s._sequence_position == 1
        s.cancel()


def test_required_sequence_exhausted_allows_free_steps():
    """After all required steps, additional steps are freely allowed."""
    s = _session(["step-a"])
    with s:
        t1 = s.enforce_step_pre_call(dict(_BASE_INV), step_id="step-a")
        s.enforce_step_post_call(t1, dict(_GOOD_OUTPUT))
        # Sequence exhausted — any step_id or no step_id is OK
        t2 = s.enforce_step_pre_call(dict(_BASE_INV))  # no step_id
        s.enforce_step_post_call(t2, dict(_GOOD_OUTPUT))
        s.complete()
    assert s.workflow_artifact["status"] == "COMPLETED"
