"""Tests for scaffold generation: presets, starter templates, and CLI commands."""

import pytest


# ---------------------------------------------------------------------------
# Task 1: WorkflowStarterIntegrityError
# ---------------------------------------------------------------------------

def test_workflow_starter_integrity_error_importable():
    from aigc import WorkflowStarterIntegrityError
    err = WorkflowStarterIntegrityError("bad starter", details={"profile": "minimal"})
    assert err.code == "WORKFLOW_STARTER_INTEGRITY_ERROR"
    assert "bad starter" in str(err)
    assert err.details["profile"] == "minimal"


def test_workflow_starter_integrity_error_is_governance_violation():
    from aigc import WorkflowStarterIntegrityError, GovernanceViolationError
    err = WorkflowStarterIntegrityError("test")
    assert isinstance(err, GovernanceViolationError)
