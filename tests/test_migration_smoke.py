"""Smoke tests for migration examples and pattern correctness."""

import importlib.util
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "migration"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden_replays"


def _load_example_module(name: str):
    """Dynamically import an example module from examples/migration/."""
    path = EXAMPLES_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_invocation_only_example_is_importable():
    """examples/migration/invocation_only.py loads without error."""
    mod = _load_example_module("invocation_only")
    assert hasattr(mod, "run_with_invocation_only")


def test_workflow_adoption_example_is_importable():
    """examples/migration/workflow_adoption.py loads without error."""
    mod = _load_example_module("workflow_adoption")
    assert hasattr(mod, "run_with_workflow_adoption")


def test_invocation_only_example_no_internal_imports():
    """invocation_only.py must not import from aigc._internal."""
    import ast
    source = (EXAMPLES_DIR / "invocation_only.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "_internal" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "_internal" not in module


def test_workflow_adoption_example_no_internal_imports():
    """workflow_adoption.py must not import from aigc._internal."""
    import ast
    source = (EXAMPLES_DIR / "workflow_adoption.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "_internal" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "_internal" not in module


def test_migration_guide_exists():
    """docs/migration.md exists."""
    guide = Path(__file__).resolve().parent.parent / "docs" / "migration.md"
    assert guide.exists(), "docs/migration.md must exist"
    content = guide.read_text()
    assert "open_session" in content
    assert "enforce_step_pre_call" in content


def _write_minimal_policy(tmp_path: Path) -> Path:
    """Write a minimal valid policy to tmp_path/policy.yaml."""
    policy = tmp_path / "policy.yaml"
    policy.write_text('policy_version: "1.0"\nroles:\n  - ai-assistant\n', encoding="utf-8")
    return policy


def test_invocation_only_example_runs(tmp_path):
    """invocation_only.py run_with_invocation_only() returns two audit artifacts."""
    policy = _write_minimal_policy(tmp_path)
    mod = _load_example_module("invocation_only")
    artifacts = mod.run_with_invocation_only(policy_file=str(policy))
    assert len(artifacts) == 2
    assert all("enforcement_result" in a for a in artifacts)


def test_workflow_adoption_example_runs(tmp_path):
    """workflow_adoption.py run_with_workflow_adoption() returns COMPLETED artifact."""
    policy = _write_minimal_policy(tmp_path)
    mod = _load_example_module("workflow_adoption")
    artifact = mod.run_with_workflow_adoption(policy_file=str(policy))
    assert artifact["status"] == "COMPLETED"
    assert len(artifact["steps"]) == 2


def test_migration_produces_same_step_count(tmp_path):
    """Both patterns govern the same two prompts — step count matches."""
    policy = _write_minimal_policy(tmp_path)
    before = _load_example_module("invocation_only")
    after = _load_example_module("workflow_adoption")

    invocation_artifacts = before.run_with_invocation_only(policy_file=str(policy))
    workflow_artifact = after.run_with_workflow_adoption(policy_file=str(policy))

    assert len(invocation_artifacts) == len(workflow_artifact["steps"])
