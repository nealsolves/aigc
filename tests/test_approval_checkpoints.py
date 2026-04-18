"""
PR-08 approval checkpoint tests: auditable pause/resume metadata.
"""
from __future__ import annotations
import pytest
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import SessionStateError

POLICY = "tests/golden_replays/golden_policy_v1.yaml"

_BASE_INV = {
    "policy_file": POLICY,
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "planner",
    "input": {"query": "test"},
    "context": {"role_declared": True, "schema_exists": True},
}

_GOOD_OUTPUT = {"result": "answer", "confidence": 0.95}


def _aigc() -> AIGC:
    return AIGC()


# ---------------------------------------------------------------------------
# Backward-compatible bare pause/resume still works
# ---------------------------------------------------------------------------

def test_bare_pause_resume_still_works():
    """pause() and resume() with no args must not break existing behavior."""
    a = _aigc()
    with a.open_session() as session:
        token = session.enforce_step_pre_call(dict(_BASE_INV))
        session.pause()
        session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
        session.resume()
        session.complete()
    assert session.workflow_artifact["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# Approval checkpoint metadata
# ---------------------------------------------------------------------------

def test_pause_with_metadata_records_checkpoint():
    """pause(approval_id=, approver_id=, reason=) records a checkpoint."""
    a = _aigc()
    with a.open_session() as session:
        token = session.enforce_step_pre_call(dict(_BASE_INV))
        session.pause(
            approval_id="chk-001",
            approver_id="reviewer-1",
            reason="Requires human review",
        )
        session.enforce_step_post_call(token, dict(_GOOD_OUTPUT))
        session.resume(
            approval_id="chk-001",
            approver_id="reviewer-1",
            approval_note="Reviewed and approved",
        )
        session.complete()

    artifact = session.workflow_artifact
    checkpoints = artifact.get("approval_checkpoints", [])
    assert len(checkpoints) == 1
    chk = checkpoints[0]
    assert chk["checkpoint_id"] == "chk-001"
    assert chk["approver_id"] == "reviewer-1"
    assert chk["reason"] == "Requires human review"
    assert chk["status"] == "approved"
    assert chk["approval_note"] == "Reviewed and approved"
    assert chk["paused_at"] is not None
    assert chk["resumed_at"] is not None


def test_bare_pause_autogenerates_checkpoint_id():
    """pause() without approval_id must still record a checkpoint with a generated id."""
    a = _aigc()
    with a.open_session() as session:
        session.pause()
        session.resume()
        session.complete()

    artifact = session.workflow_artifact
    checkpoints = artifact.get("approval_checkpoints", [])
    assert len(checkpoints) == 1
    assert checkpoints[0]["checkpoint_id"]  # non-empty string


def test_multiple_pause_resume_cycles_record_all_checkpoints():
    """Two pause/resume cycles must each produce a checkpoint record."""
    a = _aigc()
    with a.open_session() as session:
        token1 = session.enforce_step_pre_call(dict(_BASE_INV))
        session.pause(approval_id="chk-1", reason="First review")
        session.enforce_step_post_call(token1, dict(_GOOD_OUTPUT))
        session.resume(approval_id="chk-1")

        token2 = session.enforce_step_pre_call(dict(_BASE_INV))
        session.pause(approval_id="chk-2", reason="Second review")
        session.enforce_step_post_call(token2, dict(_GOOD_OUTPUT))
        session.resume(approval_id="chk-2")

        session.complete()

    artifact = session.workflow_artifact
    assert len(artifact.get("approval_checkpoints", [])) == 2


def test_canceled_session_includes_pending_checkpoint():
    """Canceling a paused session records a checkpoint with status='pending'."""
    a = _aigc()
    with a.open_session() as session:
        session.pause(approval_id="chk-deny", reason="Awaiting decision")
        session.cancel()

    artifact = session.workflow_artifact
    checkpoints = artifact.get("approval_checkpoints", [])
    assert len(checkpoints) == 1
    assert checkpoints[0]["status"] == "pending"
    assert checkpoints[0]["resumed_at"] is None


# ---------------------------------------------------------------------------
# Fix 5: approval_id mismatch must be rejected
# ---------------------------------------------------------------------------

def test_resume_with_wrong_approval_id_raises():
    """resume() with a mismatched approval_id must reject without silently approving."""
    a = _aigc()
    with pytest.raises(SessionStateError) as exc_info:
        with a.open_session() as session:
            session.pause(approval_id="chk-correct")
            session.resume(approval_id="chk-wrong")
    assert exc_info.value.code == "WORKFLOW_INVALID_TRANSITION"
    # The checkpoint must remain pending — the session was not silently approved
    assert "expected_approval_id" in exc_info.value.details


def test_resume_with_correct_approval_id_succeeds():
    """resume() with the matching approval_id must close the checkpoint."""
    a = _aigc()
    with a.open_session() as session:
        session.pause(approval_id="chk-abc")
        session.resume(approval_id="chk-abc")
        session.complete()

    artifact = session.workflow_artifact
    checkpoints = artifact.get("approval_checkpoints", [])
    assert checkpoints[0]["status"] == "approved"


def test_resume_without_approval_id_closes_pending_regardless():
    """resume() with no approval_id must close the most recent pending checkpoint."""
    a = _aigc()
    with a.open_session() as session:
        session.pause(approval_id="chk-xyz")
        session.resume()  # no approval_id — must still close it
        session.complete()

    artifact = session.workflow_artifact
    assert artifact["approval_checkpoints"][0]["status"] == "approved"


# ---------------------------------------------------------------------------
# Fail-closed: complete() must not proceed with unresolved checkpoints
# ---------------------------------------------------------------------------

def test_complete_with_pending_checkpoint_raises():
    """complete() must raise SessionStateError when a checkpoint is still pending."""
    a = _aigc()
    with pytest.raises(SessionStateError) as exc_info:
        with a.open_session() as session:
            session.pause(approval_id="chk-pending")
            # deliberately skip resume() — checkpoint remains pending
            session.complete()
    assert exc_info.value.code == "WORKFLOW_INVALID_TRANSITION"
    assert exc_info.value.details["pending_checkpoint_id"] == "chk-pending"


def test_complete_with_all_checkpoints_resolved_succeeds():
    """complete() must succeed once all checkpoints have been resolved via resume()."""
    a = _aigc()
    with a.open_session() as session:
        session.pause(approval_id="chk-resolve")
        session.resume(approval_id="chk-resolve")
        session.complete()

    artifact = session.workflow_artifact
    assert artifact["status"] == "COMPLETED"
    assert artifact["approval_checkpoints"][0]["status"] == "approved"


# ---------------------------------------------------------------------------
# Phase 2: deny_approval() semantics
# ---------------------------------------------------------------------------

def test_deny_approval_blocks_complete():
    """deny_approval() must leave the session in a state where complete() raises."""
    a = _aigc()
    with pytest.raises(SessionStateError) as exc_info:
        with a.open_session() as session:
            session.pause(approval_id="chk-denied")
            session.deny_approval(denial_reason="Rejected")
            session.complete()
    assert exc_info.value.code == "WORKFLOW_INVALID_TRANSITION"


def test_denial_reason_recorded_in_artifact():
    """deny_approval() must record denial_reason and status='denied' in the artifact."""
    a = _aigc()
    with a.open_session() as session:
        session.pause(approval_id="chk-sec")
        session.deny_approval(denial_reason="Rejected by security team")
        session.cancel()

    artifact = session.workflow_artifact
    checkpoints = artifact.get("approval_checkpoints", [])
    assert len(checkpoints) == 1
    chk = checkpoints[0]
    assert chk["status"] == "denied"
    assert chk["denial_reason"] == "Rejected by security team"


def test_denied_checkpoint_keeps_session_paused():
    """deny_approval() must leave the session in PAUSED state."""
    a = _aigc()
    with a.open_session() as session:
        session.pause(approval_id="chk-stay-paused")
        session.deny_approval(denial_reason="Denied")
        assert session._state == "PAUSED"
        session.cancel()


def test_approved_checkpoint_allows_complete():
    """Regression: pause + resume + complete must still produce a COMPLETED artifact."""
    a = _aigc()
    with a.open_session() as session:
        session.pause(approval_id="chk-happy")
        session.resume(approval_id="chk-happy")
        session.complete()

    artifact = session.workflow_artifact
    assert artifact["status"] == "COMPLETED"
    assert artifact["approval_checkpoints"][0]["status"] == "approved"
