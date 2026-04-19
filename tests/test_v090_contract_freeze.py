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

    # PR-08+ public additions not shipped in beta yet
    for name in (
        "AgentIdentity",
        "AgentCapabilityManifest",
        "ValidatorHook",
        "BedrockTraceAdapter",
        "A2AAdapter",
    ):
        assert not hasattr(aigc, name), f"aigc.{name} should not ship in v0.9.0 beta"


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


# ---------------------------------------------------------------------------
# PR-06 contract tests
# ---------------------------------------------------------------------------

def test_v090_pr06_workflow_help_lists_lint_and_doctor():
    """aigc workflow --help must list init, lint, and doctor subcommands."""
    result = subprocess.run(
        [sys.executable, "-m", "aigc", "workflow", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    assert "lint" in result.stdout, "workflow --help does not list 'lint'"
    assert "doctor" in result.stdout, "workflow --help does not list 'doctor'"
    assert "init" in result.stdout, "workflow --help does not list 'init'"


def test_v090_pr06_all_seven_reason_codes_importable():
    """All 7 frozen reason-code error classes must be importable from aigc."""
    from aigc import (
        WorkflowStarterIntegrityError,      # PR-05
        WorkflowApprovalRequiredError,       # PR-06
        WorkflowSourceRequiredError,         # PR-06
        WorkflowToolBudgetExceededError,     # PR-06
        WorkflowUnsupportedBindingError,     # PR-06
        WorkflowSessionTokenInvalidError,    # PR-06
    )
    from aigc import SessionStateError  # WORKFLOW_INVALID_TRANSITION (PR-04)

    assert WorkflowStarterIntegrityError("x").code == "WORKFLOW_STARTER_INTEGRITY_ERROR"
    assert WorkflowApprovalRequiredError("x").code == "WORKFLOW_APPROVAL_REQUIRED"
    assert WorkflowSourceRequiredError("x").code == "WORKFLOW_SOURCE_REQUIRED"
    assert WorkflowToolBudgetExceededError("x").code == "WORKFLOW_TOOL_BUDGET_EXCEEDED"
    assert WorkflowUnsupportedBindingError("x").code == "WORKFLOW_UNSUPPORTED_BINDING"
    assert WorkflowSessionTokenInvalidError("x").code == "WORKFLOW_SESSION_TOKEN_INVALID"
    assert SessionStateError("x").code == "WORKFLOW_INVALID_TRANSITION"


def test_v090_pr08_public_workflow_errors_exported():
    """PR-08 workflow-step errors raised by public methods must be public imports."""
    from aigc import (
        WorkflowHandoffDeniedError,
        WorkflowHookDeniedError,
        WorkflowParticipantMismatchError,
        WorkflowProtocolViolationError,
        WorkflowRoleViolationError,
        WorkflowSequenceViolationError,
        WorkflowStepBudgetExceededError,
        WorkflowTransitionDeniedError,
    )

    assert WorkflowParticipantMismatchError("x").code == "WORKFLOW_PARTICIPANT_MISMATCH"
    assert WorkflowSequenceViolationError("x").code == "WORKFLOW_SEQUENCE_VIOLATION"
    assert WorkflowTransitionDeniedError("x").code == "WORKFLOW_TRANSITION_DENIED"
    assert WorkflowRoleViolationError("x").code == "WORKFLOW_ROLE_VIOLATION"
    assert WorkflowProtocolViolationError("x").code == "WORKFLOW_PROTOCOL_VIOLATION"
    assert WorkflowHandoffDeniedError("x").code == "WORKFLOW_HANDOFF_DENIED"
    assert WorkflowStepBudgetExceededError("x").code == "WORKFLOW_STEP_BUDGET_EXCEEDED"
    assert WorkflowHookDeniedError("x").code == "WORKFLOW_HOOK_DENIED"


def test_v090_pr06_workflow_lint_cli_exits_cleanly_on_valid_policy(tmp_path):
    """aigc workflow lint on a valid policy exits 0."""
    policy = tmp_path / "policy.yaml"
    policy.write_text('policy_version: "1.0"\nroles:\n  - ai-assistant\n', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "aigc", "workflow", "lint", str(policy)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"workflow lint failed: {result.stderr}\n{result.stdout}"
    assert "OK" in result.stdout


def test_v090_pr06_workflow_lint_cli_exits_1_on_invalid_policy(tmp_path):
    """aigc workflow lint on an invalid policy exits 1."""
    policy = tmp_path / "bad.yaml"
    policy.write_text("roles: [unclosed", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "aigc", "workflow", "lint", str(policy)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1


def test_v090_pr06_workflow_doctor_cli_exits_cleanly_on_valid_policy(tmp_path):
    """aigc workflow doctor on a valid policy exits 0."""
    policy = tmp_path / "policy.yaml"
    policy.write_text('policy_version: "1.0"\nroles:\n  - ai-assistant\n', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "aigc", "workflow", "doctor", str(policy)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"workflow doctor failed: {result.stderr}\n{result.stdout}"


# ---------------------------------------------------------------------------
# PR-08 contract freeze tests (Phase 6 diagnostics)
# ---------------------------------------------------------------------------

def test_freeze_expected_reason_codes_unchanged():
    """
    EXPECTED_REASON_CODES must have exactly 7 entries — the OQ-7 decision removed
    WORKFLOW_STEP_BUDGET_EXCEEDED and WORKFLOW_HOOK_DENIED from the frozen public list.
    """
    assert len(EXPECTED_REASON_CODES) == 7, (
        f"EXPECTED_REASON_CODES must have exactly 7 entries, got {len(EXPECTED_REASON_CODES)}: "
        f"{EXPECTED_REASON_CODES}"
    )
    assert "WORKFLOW_STEP_BUDGET_EXCEEDED" not in EXPECTED_REASON_CODES, (
        "WORKFLOW_STEP_BUDGET_EXCEEDED was removed from the frozen public list (OQ-7)"
    )
    assert "WORKFLOW_HOOK_DENIED" not in EXPECTED_REASON_CODES, (
        "WORKFLOW_HOOK_DENIED was removed from the frozen public list (OQ-7)"
    )


def test_worktree_claude_md_does_not_add_step_budget_or_hook_denied_to_frozen_list():
    """
    The worktree CLAUDE.md must not list WORKFLOW_STEP_BUDGET_EXCEEDED or
    WORKFLOW_HOOK_DENIED in the 'Minimum first-user reason codes' line.
    These were removed by the OQ-7 decision.
    """
    claude_md_path = Path(__file__).resolve().parents[1] / "CLAUDE.md"
    assert claude_md_path.exists(), f"CLAUDE.md not found at {claude_md_path}"
    text = claude_md_path.read_text(encoding="utf-8")

    # Find the line with the frozen reason codes
    frozen_line = ""
    for line in text.splitlines():
        if "Minimum first-user reason codes" in line:
            frozen_line = line
            break

    assert frozen_line, "Could not find 'Minimum first-user reason codes' line in CLAUDE.md"
    assert "WORKFLOW_STEP_BUDGET_EXCEEDED" not in frozen_line, (
        "CLAUDE.md must not list WORKFLOW_STEP_BUDGET_EXCEEDED in the frozen reason codes "
        "(removed by OQ-7 decision)"
    )
    assert "WORKFLOW_HOOK_DENIED" not in frozen_line, (
        "CLAUDE.md must not list WORKFLOW_HOOK_DENIED in the frozen reason codes "
        "(removed by OQ-7 decision)"
    )
