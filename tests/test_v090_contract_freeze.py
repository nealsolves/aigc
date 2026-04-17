from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import aigc
from aigc import AIGC, PreCallResult


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_doc_parity.py"
EXPECTED_CLI_COMMANDS = [
    "aigc policy init",
    "aigc workflow init",
    "aigc workflow lint",
    "aigc workflow doctor",
    "aigc workflow trace",
    "aigc workflow export",
]
EXPECTED_SCAFFOLD_PROFILES = [
    "minimal",
    "standard",
    "regulated-high-assurance",
]
EXPECTED_STARTER_COVERAGE = [
    "local multi-step review",
    "approval checkpoint",
    "source required",
    "tool budget",
]
EXPECTED_REASON_CODES = [
    "WORKFLOW_INVALID_TRANSITION",
    "WORKFLOW_APPROVAL_REQUIRED",
    "WORKFLOW_SOURCE_REQUIRED",
    "WORKFLOW_TOOL_BUDGET_EXCEEDED",
    "WORKFLOW_UNSUPPORTED_BINDING",
    "WORKFLOW_SESSION_TOKEN_INVALID",
    "WORKFLOW_STARTER_INTEGRITY_ERROR",
]
EXPECTED_DOCS_ORDER = [
    "workflow quickstart",
    "migration from invocation-only to workflow",
    "troubleshooting and workflow doctor / workflow lint guide",
    "starter recipes and starter index",
    "workflow CLI guide",
    "public API boundary and integration contract",
    "supported environments",
    "operations runbook",
    "adapter docs as advanced follow-on material",
]


def _load_doc_parity_module():
    spec = importlib.util.spec_from_file_location("check_doc_parity_test", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v090_pr05_contract_truth_passes_for_repo():
    module = _load_doc_parity_module()
    assert module.check_v090_pr05_contract() == []


def test_v090_golden_path_lists_are_frozen_in_plan_and_hld():
    module = _load_doc_parity_module()

    plan_text = (REPO_ROOT / "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md").read_text(
        encoding="utf-8"
    )
    hld_text = (REPO_ROOT / "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md").read_text(
        encoding="utf-8"
    )

    assert module._extract_bullets_after_label(
        plan_text, "Frozen CLI command inventory:"
    ) == EXPECTED_CLI_COMMANDS
    assert module._extract_bullets_after_label(
        hld_text, "Frozen CLI command inventory:"
    ) == EXPECTED_CLI_COMMANDS
    assert module._extract_bullets_after_label(
        plan_text, "Frozen scaffold profiles:"
    ) == EXPECTED_SCAFFOLD_PROFILES
    assert module._extract_bullets_after_label(
        hld_text, "Frozen scaffold profiles:"
    ) == EXPECTED_SCAFFOLD_PROFILES
    assert module._extract_bullets_after_label(
        plan_text, "Required starter coverage:"
    ) == EXPECTED_STARTER_COVERAGE
    assert module._extract_bullets_after_label(
        hld_text, "Required starter coverage:"
    ) == EXPECTED_STARTER_COVERAGE
    assert module._extract_bullets_after_label(
        plan_text, "Frozen first-user diagnostic reason codes:"
    ) == EXPECTED_REASON_CODES
    assert module._extract_bullets_after_label(
        hld_text, "Frozen first-user diagnostic reason codes:"
    ) == EXPECTED_REASON_CODES
    assert module._extract_numbered_items_after_label(
        plan_text, "Frozen first-adopter docs order:"
    ) == EXPECTED_DOCS_ORDER
    assert module._extract_numbered_items_after_label(
        hld_text, "Frozen first-adopter docs order:"
    ) == EXPECTED_DOCS_ORDER


def test_v090_public_surface_includes_session_primitives():
    assert PreCallResult is not None
    assert hasattr(aigc, "PreCallResult")
    assert hasattr(aigc, "enforce_pre_call")
    assert hasattr(aigc, "enforce_post_call")

    # PR-04 surfaces — must now be importable from aigc (module-level class exports)
    assert hasattr(aigc, "GovernanceSession"), "GovernanceSession must ship in PR-04"
    assert hasattr(aigc, "SessionPreCallResult"), "SessionPreCallResult must ship in PR-04"

    # open_session is an INSTANCE METHOD on AIGC, NOT a module-level export
    assert not hasattr(aigc, "open_session"), (
        "open_session must not be a module-level export — "
        "it is instance-scoped via AIGC.open_session()"
    )
    assert callable(getattr(aigc.AIGC(), "open_session", None)), (
        "AIGC instances must have open_session as a callable method"
    )

    # PR-05+ surfaces — must not exist yet
    for name in (
        "AgentIdentity",
        "AgentCapabilityManifest",
        "ValidatorHook",
        "BedrockTraceAdapter",
        "A2AAdapter",
    ):
        assert not hasattr(aigc, name), f"aigc.{name} should not ship until PR-05+"


def test_v090_cli_surface_has_workflow_and_policy_init_commands():
    result = subprocess.run(
        [sys.executable, "-m", "aigc", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "workflow" in result.stdout
    assert "policy" in result.stdout

    policy_help = subprocess.run(
        [sys.executable, "-m", "aigc", "policy", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert policy_help.returncode in (0, 1), policy_help.stderr
    assert "init" in policy_help.stdout

    workflow_help = subprocess.run(
        [sys.executable, "-m", "aigc", "workflow", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert workflow_help.returncode in (0, 1), workflow_help.stderr
    assert "init" in workflow_help.stdout


def test_v090_public_examples_and_demo_use_public_imports_only():
    public_files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "PROJECT.md",
        REPO_ROOT / "docs/PUBLIC_INTEGRATION_CONTRACT.md",
        REPO_ROOT / "docs/INTEGRATION_GUIDE.md",
        REPO_ROOT / "demo-app-api/main.py",
    ]

    for path in public_files:
        text = path.read_text(encoding="utf-8")
        assert not re.search(
            r"(^|\n)\s*(from|import)\s+aigc\._internal",
            text,
        ), f"{path} leaks internal imports"


def test_v090_pr05_preset_classes_importable():
    """MinimalPreset, StandardPreset, RegulatedHighAssurancePreset must be importable."""
    import aigc.presets as presets

    assert hasattr(presets, "MinimalPreset"), "MinimalPreset missing from aigc.presets"
    assert hasattr(presets, "StandardPreset"), "StandardPreset missing from aigc.presets"
    assert hasattr(
        presets, "RegulatedHighAssurancePreset"
    ), "RegulatedHighAssurancePreset missing from aigc.presets"


def test_v090_pr05_workflow_init_cli_exits_cleanly(tmp_path):
    """aigc workflow init with a profile creates files without error."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "aigc",
            "workflow",
            "init",
            "--profile",
            "minimal",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"workflow init failed: {result.stderr}"
    generated_files = list(tmp_path.iterdir())
    assert generated_files, "No files generated by aigc workflow init"


def test_v090_pr05_policy_init_cli_exits_cleanly(tmp_path):
    """aigc policy init writes a policy file without error."""
    output_path = tmp_path / "policy.yaml"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "aigc",
            "policy",
            "init",
            "--profile",
            "minimal",
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"policy init failed: {result.stderr}"
    assert output_path.exists(), "policy init did not create output file"


def test_v090_pr05_workflow_starter_integrity_error_importable():
    """WorkflowStarterIntegrityError must be importable from the public aigc namespace."""
    from aigc import WorkflowStarterIntegrityError

    assert WorkflowStarterIntegrityError is not None
