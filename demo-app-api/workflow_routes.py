"""
v0.9.0 workflow governance demo routes.

Uses real AIGC.open_session() — no fake backend behavior.
All imports are from the public aigc API only (no aigc._internal).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

import aigc.presets as presets
from aigc import AIGC, ProvenanceGate

router = APIRouter(prefix="/api/workflow/v090", tags=["workflow-v090"])

# Module-level state
_last_failed_artifact: dict | None = None
# Directory written by the failure scenario so that /diagnose can run
# `aigc workflow doctor <dir>` and detect WORKFLOW_SOURCE_REQUIRED.
_last_failure_starter_dir: str | None = None
_policy_cache: dict[str, str] = {}


def _get_policy_path(profile: str) -> str:
    """Write preset policy YAML to a tempfile, cache and return the path."""
    if profile in _policy_cache:
        return _policy_cache[profile]
    preset_map = {
        "minimal": presets.MinimalPreset,
        "standard": presets.StandardPreset,
        "regulated": presets.RegulatedHighAssurancePreset,
    }
    preset = preset_map[profile]()
    tmp = tempfile.NamedTemporaryFile(
        suffix=".yaml", prefix=f"aigc_demo_{profile}_", delete=False
    )
    tmp.write(preset.policy_yaml.encode())
    tmp.close()
    _policy_cache[profile] = tmp.name
    return tmp.name


def _sim(prompt: str) -> dict:
    return {"result": f"Response to: {prompt[:60]}"}


class WorkflowRunRequest(BaseModel):
    scenario: Literal["minimal", "standard", "failure", "regulated"]


@router.post("/run")
def run_workflow(req: WorkflowRunRequest):
    global _last_failed_artifact

    if req.scenario == "minimal":
        policy_file = _get_policy_path("minimal")
        governance = AIGC()
        with governance.open_session(policy_file=policy_file) as session:
            for prompt in ["Analyze the document.", "Summarize the findings."]:
                pre = session.enforce_step_pre_call({
                    "policy_file": policy_file,
                    "input": {"prompt": prompt},
                    "output": {},
                    "context": {"caller_id": "demo"},
                    "model_provider": "anthropic",
                    "model_identifier": "claude-sonnet-4-6",
                    "role": "ai-assistant",
                })
                session.enforce_step_post_call(pre, _sim(prompt))
            session.complete()
        return {"artifact": session.workflow_artifact, "error": None}

    elif req.scenario == "standard":
        policy_file = _get_policy_path("standard")
        governance = AIGC()
        with governance.open_session(policy_file=policy_file) as session:
            pre1 = session.enforce_step_pre_call({
                "policy_file": policy_file,
                "input": {"prompt": "Draft a proposal."},
                "output": {},
                "context": {"phase": "pre-approval", "caller_id": "demo"},
                "model_provider": "anthropic",
                "model_identifier": "claude-sonnet-4-6",
                "role": "ai-assistant",
            })
            session.enforce_step_post_call(pre1, _sim("Draft a proposal."))
            session.pause()
            session.resume()
            for prompt in ["Finalize the proposal.", "Generate summary."]:
                pre = session.enforce_step_pre_call({
                    "policy_file": policy_file,
                    "input": {"prompt": prompt},
                    "output": {},
                    "context": {"phase": "post-approval", "caller_id": "demo"},
                    "model_provider": "anthropic",
                    "model_identifier": "claude-sonnet-4-6",
                    "role": "ai-assistant",
                })
                session.enforce_step_post_call(pre, _sim(prompt))
            session.complete()
        return {"artifact": session.workflow_artifact, "error": None}

    elif req.scenario == "regulated":
        # The "fixed" regulated scenario: provenance.source_ids are present.
        # Proves the failure-and-fix path end to end — same ProvenanceGate policy,
        # but with the required source_ids supplied (the fix applied).
        policy_file = _get_policy_path("regulated")
        gate = ProvenanceGate(require_source_ids=True)
        governance = AIGC(custom_gates=[gate])
        with governance.open_session(policy_file=policy_file) as session:
            pre = session.enforce_step_pre_call({
                "policy_file": policy_file,
                "input": {"prompt": "Analyze document with provenance."},
                "output": {},
                "context": {
                    "caller_id": "demo",
                    "provenance": {"source_ids": ["doc-001", "policy-v3"]},
                },
                "model_provider": "anthropic",
                "model_identifier": "claude-sonnet-4-6",
                "role": "ai-assistant",
            })
            session.enforce_step_post_call(pre, _sim("Analyze document with provenance."))
            session.complete()
        return {"artifact": session.workflow_artifact, "error": None}

    else:  # failure
        policy_file = _get_policy_path("regulated")
        gate = ProvenanceGate(require_source_ids=True)
        governance = AIGC(custom_gates=[gate])
        caught_error = None
        session_ref = None
        try:
            with governance.open_session(policy_file=policy_file) as session:
                session_ref = session
                pre = session.enforce_step_pre_call({
                    "policy_file": policy_file,
                    "input": {"prompt": "Analyze without provenance."},
                    "output": {},
                    "context": {"caller_id": "demo"},  # no provenance.source_ids
                    "model_provider": "anthropic",
                    "model_identifier": "claude-sonnet-4-6",
                    "role": "ai-assistant",
                })
                # ProvenanceGate fires at pre_output in enforce_step_post_call:
                session.enforce_step_post_call(pre, {"result": "output"})
        except Exception as exc:
            caught_error = str(exc)

        artifact = session_ref.workflow_artifact if session_ref else {}

        # Build a minimal starter directory so `aigc workflow doctor` can detect
        # WORKFLOW_SOURCE_REQUIRED.  The doctor recognizes a valid starter directory
        # by the presence of policy.yaml + workflow_example.py + README.md, then
        # scans workflow_example.py for ProvenanceGate(require_source_ids=True).
        global _last_failure_starter_dir
        starter_dir = tempfile.mkdtemp(prefix="aigc_demo_starter_")
        Path(starter_dir, "policy.yaml").write_text(
            Path(policy_file).read_text()
        )
        Path(starter_dir, "workflow_example.py").write_text(
            "from aigc import AIGC, ProvenanceGate\n\n"
            "gate = ProvenanceGate(require_source_ids=True)\n"
            "governance = AIGC(custom_gates=[gate])\n"
        )
        Path(starter_dir, "README.md").write_text(
            "# Regulated workflow demo starter\n"
        )
        _last_failure_starter_dir = starter_dir
        _last_failed_artifact = artifact
        return {"artifact": artifact, "error": caught_error}


@router.post("/compare")
def compare_workflows():
    """Run the same prompt governed vs ungoverned and return both results."""
    policy_file = _get_policy_path("minimal")
    prompt = "Summarize the quarterly report."

    governance = AIGC()
    with governance.open_session(policy_file=policy_file) as session:
        pre = session.enforce_step_pre_call({
            "policy_file": policy_file,
            "input": {"prompt": prompt},
            "output": {},
            "context": {"caller_id": "demo"},
            "model_provider": "anthropic",
            "model_identifier": "claude-sonnet-4-6",
            "role": "ai-assistant",
        })
        session.enforce_step_post_call(pre, _sim(prompt))
        session.complete()
    governed_artifact = session.workflow_artifact

    ungoverned_artifact = {
        "status": "ok",
        "enforcement_result": "PASS",
        "policy_version": "ungoverned",
        "audit_available": False,
        "result": _sim(prompt)["result"],
    }

    return {
        "governed": {"artifact": governed_artifact, "error": None},
        "ungoverned": {"artifact": ungoverned_artifact, "error": None},
    }


@router.get("/diagnose")
def diagnose_last_failure():
    """Run aigc workflow doctor on the starter dir from the most recent failure."""
    if _last_failure_starter_dir is None:
        return {"findings": [], "source": "no_prior_failure"}

    # The doctor detects WORKFLOW_SOURCE_REQUIRED by scanning workflow_example.py
    # for ProvenanceGate(require_source_ids=True) — it needs a directory, not an
    # artifact file.  We created that directory when the failure scenario ran.
    result = subprocess.run(
        [sys.executable, "-m", "aigc", "workflow", "doctor",
         _last_failure_starter_dir, "--json"],
        capture_output=True, text=True,
    )
    # Parse findings regardless of exit code: doctor exits 1 for ERROR-severity
    # findings, which are exactly the ones we want to surface to the user.
    try:
        findings = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        findings = []
    return {"findings": findings, "source": "failure_starter_dir"}
