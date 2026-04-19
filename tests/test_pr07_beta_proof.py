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

from aigc import CustomGateViolationError


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _generate_starter(profile: str, output_dir: Path) -> Path:
    """Run aigc workflow init and return the output directory."""
    result = subprocess.run(
        [sys.executable, "-m", "aigc", "workflow", "init",
         "--profile", profile, "--output-dir", str(output_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"aigc workflow init --profile {profile} failed:\n{result.stderr}"
    )
    return output_dir


def _load_workflow_module(starter_dir: Path):
    """Load the generated workflow_example.py as an isolated module."""
    script = starter_dir / "workflow_example.py"
    spec = importlib.util.spec_from_file_location(
        f"workflow_example_{starter_dir.name}",
        script,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _exec_workflow_module(starter_dir: Path, func_name: str):
    """Load and execute the generated workflow_example.py, return the artifact."""
    mod = _load_workflow_module(starter_dir)
    return getattr(mod, func_name)()


def _break_regulated_starter(starter_dir: Path) -> str:
    workflow_py = starter_dir / "workflow_example.py"
    original_source = workflow_py.read_text(encoding="utf-8")
    broken_source = original_source.replace(
        '                    "source_ids": ["doc-001", "doc-002"],\n',
        "",
    ).replace(
        '                    "source_ids": ["analysis-step-1"],\n',
        "",
    )
    assert broken_source != original_source, "regulated starter failure edit did not apply"
    workflow_py.write_text(broken_source, encoding="utf-8")
    return original_source


def _run_broken_regulated_workflow(starter_dir: Path):
    mod = _load_workflow_module(starter_dir)
    try:
        getattr(mod, "run_regulated_workflow")()
    except Exception as exc:  # noqa: BLE001
        return getattr(mod, "LAST_WORKFLOW_ARTIFACT", None), exc
    return getattr(mod, "LAST_WORKFLOW_ARTIFACT", None), None


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
    def test_missing_source_ids_raises_custom_gate_violation(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)
        _break_regulated_starter(d)
        _, exc = _run_broken_regulated_workflow(d)
        assert isinstance(exc, CustomGateViolationError), (
            f"Expected CustomGateViolationError, got {type(exc).__name__}: {exc}"
        )

    def test_missing_source_ids_produces_failed_artifact(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)
        _break_regulated_starter(d)
        artifact, _ = _run_broken_regulated_workflow(d)
        assert artifact["status"] == "FAILED"

    def test_missing_source_ids_failed_artifact_has_failure_summary(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)
        _break_regulated_starter(d)
        artifact, _ = _run_broken_regulated_workflow(d)
        assert artifact["failure_summary"] is not None

    def test_doctor_on_regulated_starter_reports_workflow_source_required(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)
        _break_regulated_starter(d)
        _run_broken_regulated_workflow(d)

        result = subprocess.run(
            [sys.executable, "-m", "aigc", "workflow", "doctor", str(d), "--json"],
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
        _break_regulated_starter(d)
        result = subprocess.run(
            [sys.executable, "-m", "aigc", "workflow", "doctor", str(d)],
            capture_output=True, text=True,
        )
        # Doctor exits 1 only on ERROR severity; WORKFLOW_SOURCE_REQUIRED is INFO
        assert result.returncode == 0, (
            f"Doctor exited {result.returncode}:\n{result.stderr}"
        )

    def test_regulated_fixed_in_place_reaches_completed(self, tmp_path):
        d = tmp_path / "regulated"
        d.mkdir()
        _generate_starter("regulated-high-assurance", d)
        original_source = _break_regulated_starter(d)
        artifact, exc = _run_broken_regulated_workflow(d)
        assert artifact["status"] == "FAILED"
        assert isinstance(exc, CustomGateViolationError)
        (d / "workflow_example.py").write_text(original_source, encoding="utf-8")
        artifact = _exec_workflow_module(d, "run_regulated_workflow")
        assert artifact["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# Task 2.1.e  Clean-venv install gate — regression guard
#
# The validate_v090_beta_proof.py harness creates a fresh venv that reuses the
# current interpreter's installed site-packages, then runs
# `pip install --no-deps --no-build-isolation -e .` to prove the clean-env
# install works without contacting a package index. These tests guard that
# restricted-network bootstrap path.
# ---------------------------------------------------------------------------

class TestCleanEnvInstallProof:
    """Structural guards for the clean-environment install gate."""

    _SCRIPT = Path(__file__).parent.parent / "scripts" / "validate_v090_beta_proof.py"

    def test_validate_script_has_no_pypi_bootstrap_commands(self):
        """
        The harness must not bootstrap build/runtime deps by calling pip against
        a package index. Restricted-network validation should rely on
        system_site_packages=True plus a no-deps editable install.
        """
        source = self._SCRIPT.read_text()
        import re
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.search(r'["\']download["\']', stripped):
                pytest.fail(
                    "validate_v090_beta_proof.py still contains a live "
                    "`pip download` step, which reintroduces index access for "
                    f"restricted-network runs. Offending line: {stripped!r}"
                )
            if "setuptools" in stripped and "pip" in stripped:
                pytest.fail(
                    "validate_v090_beta_proof.py still shells out to pip for "
                    "setuptools bootstrap instead of relying on "
                    f"system_site_packages=True. Offending line: {stripped!r}"
                )

    def test_validate_script_uses_host_site_packages_and_no_deps_install(self):
        """
        gate_install must create the venv with system_site_packages=True and
        then install the repo with --no-deps --no-build-isolation so the run
        stays local to the current interpreter's already-installed packages.
        """
        source = self._SCRIPT.read_text()
        code = "\n".join(
            line for line in source.splitlines()
            if not line.strip().startswith("#")
        )
        assert "system_site_packages=True" in code, (
            "gate_install must create the fresh venv with system_site_packages=True "
            "so build/runtime deps remain available without index access"
        )
        assert "--no-deps" in code, (
            "gate_install must use --no-deps for the editable install so pip "
            "does not resolve dependencies from an index"
        )
        assert "--no-build-isolation" in code, (
            "gate_install must use --no-build-isolation for the editable "
            "install so pip reuses the host interpreter's already-installed "
            "build backend"
        )

    def test_validate_script_is_importable(self):
        """The harness script must be syntactically valid Python."""
        import ast
        source = self._SCRIPT.read_text()
        try:
            ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(f"validate_v090_beta_proof.py has a syntax error: {exc}")


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
