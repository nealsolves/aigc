"""End-to-end smoke tests for generated starter workflow_example.py files."""

import ast
import importlib.util
import sys
import warnings
from pathlib import Path

import pytest
import yaml

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


# ---------------------------------------------------------------------------
# Regression tests for PR-05 code review findings
# ---------------------------------------------------------------------------

class TestRoleInjectionEscaping:
    """Roles with embedded quotes must produce syntactically valid Python."""

    @pytest.mark.parametrize("render_fn,run_name", [
        (render_minimal_starter, "run_minimal_workflow"),
        (render_standard_starter, "run_standard_workflow"),
        (render_regulated_starter, "run_regulated_workflow"),
    ])
    def test_quoted_role_produces_valid_python(self, render_fn, run_name):
        files = render_fn(role='reviewer"lead')
        # ast.parse raises SyntaxError if role was injected raw
        tree = ast.parse(files["workflow_example.py"])
        # Verify the role value made it into the source
        source = files["workflow_example.py"]
        assert 'reviewer"lead' in source

    @pytest.mark.parametrize("render_fn", [
        render_minimal_starter,
        render_standard_starter,
        render_regulated_starter,
    ])
    def test_role_with_backslash_produces_valid_python(self, render_fn):
        files = render_fn(role="path\\role")
        ast.parse(files["workflow_example.py"])


class TestScriptRelativePolicyDefault:
    """Generated workflow functions must resolve policy.yaml relative to __file__."""

    def test_minimal_workflow_default_resolves_script_dir(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_minimal_starter)
        # Call without explicit policy_file; the default should find tmp_path/policy.yaml
        artifact = mod.run_minimal_workflow()
        assert artifact["status"] == "COMPLETED"

    def test_standard_workflow_default_resolves_script_dir(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_standard_starter)
        artifact = mod.run_standard_workflow()
        assert artifact["status"] == "COMPLETED"

    def test_regulated_workflow_default_resolves_script_dir(self, tmp_path):
        mod = _write_starter_and_load(tmp_path, render_regulated_starter)
        artifact = mod.run_regulated_workflow()
        assert artifact["status"] == "COMPLETED"

    def test_generated_source_contains_file_reference(self):
        """Template must use __file__ for policy resolution, not a bare string."""
        for render_fn in (render_minimal_starter, render_standard_starter, render_regulated_starter):
            source = render_fn()["workflow_example.py"]
            assert "__file__" in source, f"{render_fn.__name__} missing __file__ reference"


class TestPresetPreconditions:
    """Preset policies must declare pre_conditions.required to avoid runtime warnings."""

    @pytest.mark.parametrize("render_fn,run_fn_name", [
        (render_minimal_starter, "run_minimal_workflow"),
        (render_standard_starter, "run_standard_workflow"),
        (render_regulated_starter, "run_regulated_workflow"),
    ])
    def test_preset_policy_has_preconditions_required(self, render_fn, run_fn_name):
        files = render_fn()
        policy = yaml.safe_load(files["policy.yaml"])
        assert "pre_conditions" in policy, "policy.yaml missing pre_conditions"
        assert "required" in policy["pre_conditions"], "pre_conditions missing required"
        assert policy["pre_conditions"]["required"], "pre_conditions.required is empty"

    @pytest.mark.parametrize("render_fn,run_fn_name", [
        (render_minimal_starter, "run_minimal_workflow"),
        (render_standard_starter, "run_standard_workflow"),
        (render_regulated_starter, "run_regulated_workflow"),
    ])
    def test_starter_workflow_emits_no_precondition_warning(
        self, tmp_path, render_fn, run_fn_name
    ):
        mod = _write_starter_and_load(tmp_path, render_fn)
        run_fn = getattr(mod, run_fn_name)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            run_fn(policy_file=str(tmp_path / "policy.yaml"))
        precond_warnings = [
            w for w in caught
            if "pre_conditions" in str(w.message)
        ]
        assert not precond_warnings, (
            f"Unexpected pre_conditions warning from {render_fn.__name__}: "
            + "; ".join(str(w.message) for w in precond_warnings)
        )
