"""
PR-07 mandatory stop-ship proof tests.

Validates the default v0.9.0 adopter journey end-to-end:
  1. Minimal starter -> COMPLETED
  2. Standard starter -> COMPLETED with approval flow
  3. Regulated failure path:
       a. Invocation without source_ids -> CustomGateViolationError from
          enforce_step_post_call (ProvenanceGate runs at INSERTION_PRE_OUTPUT)
          -> session artifact FAILED
       b. aigc workflow doctor starter_dir/ -> WORKFLOW_SOURCE_REQUIRED finding
       c. Unmodified starter (source_ids present) -> COMPLETED
  4. Public-import boundary -- no aigc._internal in generated starters or
     migration examples
"""
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from aigc import AIGC, CustomGateViolationError, ProvenanceGate


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _generate_starter(profile: str, output_dir: Path) -> Path:
    """Run aigc workflow init and return the output directory."""
    result = subprocess.run(
        ["aigc", "workflow", "init",
         "--profile", profile, "--output-dir", str(output_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"aigc workflow init --profile {profile} failed:\n{result.stderr}"
    )
    return output_dir


def _exec_workflow_module(starter_dir: Path, func_name: str):
    """Load and execute the generated workflow_example.py, return the artifact."""
    script = starter_dir / "workflow_example.py"
    spec = importlib.util.spec_from_file_location("workflow_example", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, func_name)()


def _collect_imports(source: str) -> list[str]:
    """Return all ImportFrom module strings in the given Python source."""
    tree = ast.parse(source)
    return [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]


# ---------------------------------------------------------------------------
# Task 2.1.a  Minimal starter
# ---------------------------------------------------------------------------

class TestMinimalBetaProof:
    def test_minimal_starter_workflow_reaches_completed(self, tmp_path):
        d = tmp_path / "minimal"
        d.mkdir()
        _generate_starter("minimal", d)
        artifact = _exec_workflow_module(d, "run_minimal_workflow")
        assert artifact["status"] == "COMPLETED"

    def test_minimal_workflow_has_two_steps(self, tmp_path):
        d = tmp_path / "minimal"
        d.mkdir()
        _generate_starter("minimal", d)
        artifact = _exec_workflow_module(d, "run_minimal_workflow")
        assert len(artifact["steps"]) == 2

    def test_minimal_workflow_artifact_no_failure_summary(self, tmp_path):
        d = tmp_path / "minimal"
        d.mkdir()
        _generate_starter("minimal", d)
        artifact = _exec_workflow_module(d, "run_minimal_workflow")
        assert artifact.get("failure_summary") is None

    def test_minimal_workflow_uses_public_imports_only(self, tmp_path):
        d = tmp_path / "minimal"
        d.mkdir()
        _generate_starter("minimal", d)
        source = (d / "workflow_example.py").read_text()
        for module in _collect_imports(source):
            assert "_internal" not in module, (
                f"Found internal import '{module}' in minimal starter"
            )


# ---------------------------------------------------------------------------
# Task 2.1.b  Standard starter
# ---------------------------------------------------------------------------

class TestStandardBetaProof:
    def test_standard_starter_workflow_reaches_completed(self, tmp_path):
        d = tmp_path / "standard"
        d.mkdir()
        _generate_starter("standard", d)
        artifact = _exec_workflow_module(d, "run_standard_workflow")
        assert artifact["status"] == "COMPLETED"

    def test_standard_workflow_has_three_steps(self, tmp_path):
        d = tmp_path / "standard"
        d.mkdir()
        _generate_starter("standard", d)
        artifact = _exec_workflow_module(d, "run_standard_workflow")
        assert len(artifact["steps"]) == 3

    def test_standard_generated_script_contains_pause_resume(self, tmp_path):
        d = tmp_path / "standard"
        d.mkdir()
        _generate_starter("standard", d)
        source = (d / "workflow_example.py").read_text()
        assert "session.pause()" in source
        assert "session.resume()" in source


# ---------------------------------------------------------------------------
# Task 2.1.c  Regulated failure-and-fix path
#
# ProvenanceGate runs at INSERTION_PRE_OUTPUT (inside enforce_step_post_call).
# Steps:
#   1. enforce_step_pre_call with no provenance -> succeeds
#   2. enforce_step_post_call with no provenance -> raises CustomGateViolationError
#   3. GovernanceSession.__exit__ catches it -> transitions to FAILED, emits artifact
# ---------------------------------------------------------------------------

class TestRegulatedBetaProof:

    def _run_step_without_source_ids(self, policy_file: str):
        """
        Run one governed step with no provenance context.
        Returns (artifact, exc_or_None).
        ProvenanceGate fires at pre_output (inside enforce_step_post_call).
        """
        gate = ProvenanceGate(require_source_ids=True)
        governance = AIGC(custom_gates=[gate])
        caught_exc = None
        session_ref = None

        try:
            with governance.open_session(policy_file=policy_file) as session:
                session_ref = session
                # pre_call succeeds - gate not yet invoked
                pre = session.enforce_step_pre_call({
                    "policy_file": policy_file,
                    "input": {"prompt": "Analyze."},
                    "output": {},
                    "context": {"caller_id": "test"},   # no provenance.source_ids
                    "model_provider": "anthropic",
                    "model_identifier": "claude-sonnet-4-6",
                    "role": "ai-assistant",
                })
                # post_call raises - ProvenanceGate fires at INSERTION_PRE_OUTPUT
                session.enforce_step_post_call(pre, {"result": "output"})
        except Exception as exc:
            caught_exc = exc

        return session_ref.workflow_artifact, caught_exc

    def test_missing_source_ids_raises_custom_gate_violation(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)
        _, exc = self._run_step_without_source_ids(str(d / "policy.yaml"))
        assert isinstance(exc, CustomGateViolationError), (
            f"Expected CustomGateViolationError, got {type(exc).__name__}: {exc}"
        )

    def test_missing_source_ids_produces_failed_artifact(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)
        artifact, _ = self._run_step_without_source_ids(str(d / "policy.yaml"))
        assert artifact["status"] == "FAILED"

    def test_missing_source_ids_failed_artifact_has_failure_summary(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)
        artifact, _ = self._run_step_without_source_ids(str(d / "policy.yaml"))
        assert artifact["failure_summary"] is not None

    def test_doctor_on_regulated_starter_reports_workflow_source_required(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)

        result = subprocess.run(
            ["aigc", "workflow", "doctor", str(d), "--json"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"aigc workflow doctor exited {result.returncode}:\n{result.stderr}"
        )
        findings = json.loads(result.stdout)
        codes = [f["code"] for f in findings]
        assert "WORKFLOW_SOURCE_REQUIRED" in codes, (
            f"Expected WORKFLOW_SOURCE_REQUIRED in doctor findings. Got: {codes}"
        )

    def test_doctor_cli_exits_zero_for_advisory_findings(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)
        result = subprocess.run(
            ["aigc", "workflow", "doctor", str(d)],
            capture_output=True, text=True,
        )
        # Doctor exits 1 only on ERROR severity; WORKFLOW_SOURCE_REQUIRED is INFO
        assert result.returncode == 0, (
            f"Doctor exited {result.returncode}:\n{result.stderr}"
        )

    def test_regulated_with_source_ids_present_reaches_completed(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)
        # Run the unmodified generated script - it has source_ids in every step
        artifact = _exec_workflow_module(d, "run_regulated_workflow")
        assert artifact["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# Task 2.1.d  Public-import boundary
# ---------------------------------------------------------------------------

class TestPublicImportBoundaryProof:
    def test_no_internal_imports_in_minimal_starter(self):
        from aigc._internal.starter_templates import render_minimal_starter
        source = render_minimal_starter()["workflow_example.py"]
        for module in _collect_imports(source):
            assert "_internal" not in module, (
                f"minimal starter has internal import: '{module}'"
            )

    def test_no_internal_imports_in_standard_starter(self):
        from aigc._internal.starter_templates import render_standard_starter
        source = render_standard_starter()["workflow_example.py"]
        for module in _collect_imports(source):
            assert "_internal" not in module, (
                f"standard starter has internal import: '{module}'"
            )

    def test_no_internal_imports_in_regulated_starter(self):
        from aigc._internal.starter_templates import render_regulated_starter
        source = render_regulated_starter()["workflow_example.py"]
        for module in _collect_imports(source):
            assert "_internal" not in module, (
                f"regulated starter has internal import: '{module}'"
            )

    def test_no_internal_imports_in_migration_examples(self):
        root = Path(__file__).parent.parent
        for path in [
            root / "examples" / "migration" / "invocation_only.py",
            root / "examples" / "migration" / "workflow_adoption.py",
        ]:
            source = path.read_text()
            for module in _collect_imports(source):
                assert "_internal" not in module, (
                    f"Found internal import '{module}' in {path.name}"
                )
