from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import aigc
from aigc import AIGC, PreCallResult


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_doc_parity.py"
EXPECTED_SESSION_STATES = [
    "OPEN",
    "PAUSED",
    "FAILED",
    "COMPLETED",
    "CANCELED",
    "FINALIZED",
]
EXPECTED_WORKFLOW_STATUSES = [
    "COMPLETED",
    "FAILED",
    "CANCELED",
    "INCOMPLETE",
]


def _load_doc_parity_module():
    spec = importlib.util.spec_from_file_location("check_doc_parity_test", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v090_pr02_contract_truth_passes_for_repo():
    module = _load_doc_parity_module()
    assert module.check_v090_pr02_contract() == []


def test_v090_lifecycle_and_status_lists_are_frozen_in_plan_and_hld():
    module = _load_doc_parity_module()

    plan_text = (REPO_ROOT / "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md").read_text(
        encoding="utf-8"
    )
    hld_text = (REPO_ROOT / "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md").read_text(
        encoding="utf-8"
    )

    assert module._extract_bullets_after_label(
        plan_text, "Canonical session lifecycle states:"
    ) == EXPECTED_SESSION_STATES
    assert module._extract_bullets_after_label(
        hld_text, "Canonical lifecycle states:"
    ) == EXPECTED_SESSION_STATES
    assert module._extract_bullets_after_label(
        plan_text, "Canonical workflow artifact `status` values:"
    ) == EXPECTED_WORKFLOW_STATUSES
    assert module._extract_bullets_after_label(
        hld_text, "Canonical serialized workflow artifact `status` values:"
    ) == EXPECTED_WORKFLOW_STATUSES
    assert "`finalize()` from `OPEN` or `PAUSED` is allowed and emits `INCOMPLETE`." in plan_text
    assert "| `OPEN` or `PAUSED` finalized without terminal completion | `INCOMPLETE` |" in hld_text


def test_v090_public_surface_remains_invocation_only():
    assert PreCallResult is not None
    assert hasattr(aigc, "PreCallResult")
    assert hasattr(aigc, "enforce_pre_call")
    assert hasattr(aigc, "enforce_post_call")

    for name in (
        "GovernanceSession",
        "SessionPreCallResult",
        "AgentIdentity",
        "AgentCapabilityManifest",
        "ValidatorHook",
        "BedrockTraceAdapter",
        "A2AAdapter",
        "open_session",
    ):
        assert not hasattr(aigc, name), f"aigc.{name} should not ship in PR-02"

    assert not hasattr(AIGC, "open_session")


def test_v090_cli_surface_has_no_workflow_commands():
    result = subprocess.run(
        [sys.executable, "-m", "aigc", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "{policy,compliance}" in result.stdout
    assert "workflow" not in result.stdout


def test_v090_protocol_boundary_rules_are_frozen_in_plan_and_hld():
    plan_text = (REPO_ROOT / "docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md").read_text(
        encoding="utf-8"
    )
    hld_text = (REPO_ROOT / "docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md").read_text(
        encoding="utf-8"
    )

    assert "alias-backed participant identity" in plan_text
    assert "collaboratorName" in plan_text
    assert "supportedInterfaces[].protocolVersion" in plan_text
    assert "TASK_STATE_*" in plan_text
    assert "gRPC" in plan_text

    assert "alias-backed collaborator identity is required" in hld_text
    assert "missing trace" in hld_text
    assert "fails closed" in hld_text
    assert "supportedInterfaces[].protocolVersion" in hld_text
    assert "TASK_STATE_" in hld_text
    assert "non-normative or shorthand task-state names are rejected" in hld_text
    assert "`GRPC`" in hld_text
