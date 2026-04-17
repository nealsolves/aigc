"""End-to-end smoke tests for generated starter workflow_example.py files."""

import importlib.util
import sys
from pathlib import Path

import pytest

from aigc._internal.starter_templates import (
    render_minimal_starter,
    render_standard_starter,
    render_regulated_starter,
)


def _write_starter_and_load(tmp_path: Path, render_fn, **render_kwargs):
    """Write starter files and dynamically load workflow_example module."""
    files = render_fn(**render_kwargs)
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")

    spec = importlib.util.spec_from_file_location(
        "workflow_example",
        tmp_path / "workflow_example.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMinimalStarterSmoke:
    def test_minimal_workflow_runs_and_returns_completed(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_minimal_starter)
        artifact = mod.run_minimal_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert artifact["status"] == "COMPLETED"

    def test_minimal_workflow_has_two_steps(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_minimal_starter)
        artifact = mod.run_minimal_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert len(artifact["steps"]) == 2

    def test_minimal_workflow_artifact_has_session_id(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_minimal_starter)
        artifact = mod.run_minimal_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert "session_id" in artifact
        assert artifact["session_id"]

    def test_minimal_workflow_artifact_has_checksums(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_minimal_starter)
        artifact = mod.run_minimal_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert len(artifact["invocation_audit_checksums"]) == 2


class TestStandardStarterSmoke:
    def test_standard_workflow_runs_and_returns_completed(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_standard_starter)
        artifact = mod.run_standard_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert artifact["status"] == "COMPLETED"

    def test_standard_workflow_has_three_steps(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_standard_starter)
        artifact = mod.run_standard_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert len(artifact["steps"]) == 3

    def test_standard_workflow_approval_checkpoint_pause_resume(self, tmp_path):
        """Simulated approval proceeds: session ends COMPLETED, not CANCELED."""
        mod = _write_starter_and_load(tmp_path, render_standard_starter)
        artifact = mod.run_standard_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert artifact["status"] == "COMPLETED"

    def test_standard_workflow_approval_denial_returns_canceled(self, tmp_path):
        """When approval is denied, the workflow artifact status is CANCELED."""
        mod = _write_starter_and_load(tmp_path, render_standard_starter)
        # Monkeypatch _request_human_approval to deny
        mod._request_human_approval = lambda summary: False
        artifact = mod.run_standard_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert artifact["status"] == "CANCELED"


class TestRegulatedStarterSmoke:
    def test_regulated_workflow_runs_and_returns_completed(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_regulated_starter)
        artifact = mod.run_regulated_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert artifact["status"] == "COMPLETED"

    def test_regulated_workflow_has_two_steps(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_regulated_starter)
        artifact = mod.run_regulated_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert len(artifact["steps"]) == 2

    def test_regulated_workflow_artifact_has_session_id(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_regulated_starter)
        artifact = mod.run_regulated_workflow(policy_file=str(tmp_path / "policy.yaml"))
        assert artifact["session_id"]

    def test_regulated_workflow_rejects_missing_source_ids(self, tmp_path):
        """ProvenanceGate must reject calls that omit source IDs (fail-closed).

        ProvenanceGate runs at INSERTION_PRE_OUTPUT (post-call phase).
        The violation is raised during enforce_step_post_call, not pre-call.
        """
        import yaml
        import aigc
        from aigc import ProvenanceGate, CustomGateViolationError

        # Policy must exist so loading succeeds before custom gates are evaluated
        (tmp_path / "policy.yaml").write_text(
            yaml.dump({"policy_version": "1.0", "roles": ["ai-assistant"]})
        )

        gate = ProvenanceGate(require_source_ids=True)
        governance = aigc.AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError):
            with governance.open_session(
                policy_file=str(tmp_path / "policy.yaml")
            ) as session:
                invocation = {
                    "policy_file": str(tmp_path / "policy.yaml"),
                    "input": {"prompt": "missing source"},
                    "output": {},
                    "context": {},  # No provenance.source_ids
                    "model_provider": "anthropic",
                    "model_identifier": "claude-sonnet-4-6",
                    "role": "ai-assistant",
                }
                # pre-call succeeds; post-call raises because
                # ProvenanceGate runs at INSERTION_PRE_OUTPUT
                pre = session.enforce_step_pre_call(invocation)
                session.enforce_step_post_call(pre, {"result": "test output"})
