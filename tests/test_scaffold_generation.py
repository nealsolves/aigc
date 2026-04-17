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
