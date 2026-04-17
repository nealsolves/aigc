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


# ---------------------------------------------------------------------------
# Task 2: Thin Preset Builders
# ---------------------------------------------------------------------------

def test_minimal_preset_policy_yaml():
    from aigc.presets import MinimalPreset
    preset = MinimalPreset(role="ai-assistant")
    yaml_text = preset.policy_yaml
    assert "policy_version" in yaml_text
    assert "ai-assistant" in yaml_text
    assert preset.PROFILE == "minimal"


def test_minimal_preset_session_metadata():
    from aigc.presets import MinimalPreset
    meta = MinimalPreset().session_metadata
    assert meta["starter_profile"] == "minimal"
    assert "generated_by" in meta


def test_standard_preset_policy_yaml():
    from aigc.presets import StandardPreset
    preset = StandardPreset(role="ai-assistant")
    yaml_text = preset.policy_yaml
    assert "policy_version" in yaml_text
    assert "ai-assistant" in yaml_text
    assert preset.PROFILE == "standard"


def test_regulated_preset_policy_yaml():
    from aigc.presets import RegulatedHighAssurancePreset
    preset = RegulatedHighAssurancePreset(role="ai-assistant")
    yaml_text = preset.policy_yaml
    assert "policy_version" in yaml_text
    assert "ai-assistant" in yaml_text
    assert "document_reader" in yaml_text
    assert preset.PROFILE == "regulated-high-assurance"


def test_preset_write_policy(tmp_path):
    from aigc.presets import MinimalPreset
    import yaml
    preset = MinimalPreset(role="tester")
    out = tmp_path / "policy.yaml"
    preset.write_policy(out)
    assert out.exists()
    parsed = yaml.safe_load(out.read_text())
    assert parsed["policy_version"] == "1.0"
    assert "tester" in parsed["roles"]


def test_minimal_preset_special_character_role():
    """A role with YAML-special characters must parse back correctly."""
    import yaml
    from aigc.presets import MinimalPreset
    preset = MinimalPreset(role="ai:assistant")
    parsed = yaml.safe_load(preset.policy_yaml)
    assert "ai:assistant" in parsed["roles"]


# ---------------------------------------------------------------------------
# Task 3: Starter Templates
# ---------------------------------------------------------------------------

def test_render_minimal_starter_returns_expected_files():
    from aigc._internal.starter_templates import render_minimal_starter
    files = render_minimal_starter()
    assert set(files.keys()) == {"policy.yaml", "workflow_example.py", "README.md"}


def test_render_standard_starter_returns_expected_files():
    from aigc._internal.starter_templates import render_standard_starter
    files = render_standard_starter()
    assert set(files.keys()) == {"policy.yaml", "workflow_example.py", "README.md"}


def test_render_regulated_starter_returns_expected_files():
    from aigc._internal.starter_templates import render_regulated_starter
    files = render_regulated_starter()
    assert set(files.keys()) == {"policy.yaml", "workflow_example.py", "README.md"}


def test_minimal_starter_policy_is_valid_yaml():
    import yaml
    from aigc._internal.starter_templates import render_minimal_starter
    files = render_minimal_starter()
    parsed = yaml.safe_load(files["policy.yaml"])
    assert parsed["policy_version"] == "1.0"
    assert "ai-assistant" in parsed["roles"]


def test_regulated_starter_policy_has_tool_budget():
    import yaml
    from aigc._internal.starter_templates import render_regulated_starter
    files = render_regulated_starter()
    parsed = yaml.safe_load(files["policy.yaml"])
    assert "tools" in parsed
    assert "allowed_tools" in parsed["tools"]


def test_starter_workflow_py_no_internal_imports():
    """Generated workflow_example.py files must not import from aigc._internal."""
    import ast
    from aigc._internal.starter_templates import (
        render_minimal_starter,
        render_standard_starter,
        render_regulated_starter,
    )
    for render_fn in [render_minimal_starter, render_standard_starter, render_regulated_starter]:
        files = render_fn()
        source = files["workflow_example.py"]
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "_internal" not in alias.name, (
                        f"Internal import in starter: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "_internal" not in module, (
                    f"Internal import from in starter: {module}"
                )


def test_starter_role_customization():
    from aigc._internal.starter_templates import render_minimal_starter
    files = render_minimal_starter(role="summarizer")
    assert "summarizer" in files["policy.yaml"]


# ---------------------------------------------------------------------------
# Task 4: aigc policy init CLI command
# ---------------------------------------------------------------------------

def test_policy_init_minimal_creates_valid_yaml(tmp_path):
    import yaml
    from aigc._internal.cli import main
    out = tmp_path / "policy.yaml"
    rc = main(["policy", "init", "--profile", "minimal", "--output", str(out)])
    assert rc == 0
    assert out.exists()
    parsed = yaml.safe_load(out.read_text())
    assert parsed["policy_version"] == "1.0"
    assert "ai-assistant" in parsed["roles"]


def test_policy_init_standard_creates_yaml(tmp_path):
    import yaml
    from aigc._internal.cli import main
    out = tmp_path / "policy.yaml"
    rc = main(["policy", "init", "--profile", "standard", "--output", str(out)])
    assert rc == 0
    parsed = yaml.safe_load(out.read_text())
    assert "ai-assistant" in parsed["roles"]


def test_policy_init_regulated_creates_yaml_with_tools(tmp_path):
    import yaml
    from aigc._internal.cli import main
    out = tmp_path / "policy.yaml"
    rc = main(["policy", "init", "--profile", "regulated-high-assurance", "--output", str(out)])
    assert rc == 0
    parsed = yaml.safe_load(out.read_text())
    assert "tools" in parsed


def test_policy_init_fails_if_output_exists(tmp_path):
    from aigc._internal.cli import main
    out = tmp_path / "policy.yaml"
    out.write_text("existing content")
    rc = main(["policy", "init", "--profile", "minimal", "--output", str(out)])
    assert rc == 1
    assert out.read_text() == "existing content"


def test_policy_init_custom_role(tmp_path):
    import yaml
    from aigc._internal.cli import main
    out = tmp_path / "policy.yaml"
    rc = main(["policy", "init", "--profile", "minimal", "--role", "summarizer", "--output", str(out)])
    assert rc == 0
    parsed = yaml.safe_load(out.read_text())
    assert "summarizer" in parsed["roles"]
