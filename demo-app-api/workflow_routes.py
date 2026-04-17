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
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

import aigc.presets as presets
from aigc import AIGC, ProvenanceGate

router = APIRouter(prefix="/api/workflow/v090", tags=["workflow-v090"])

# Module-level state
_last_failed_artifact: dict | None = None
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
    scenario: Literal["minimal", "standard", "failure"]


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
    """Run aigc workflow doctor on the most recent FAILED artifact."""
    if _last_failed_artifact is None:
        return {"findings": [], "source": "no_prior_failure"}

    tmp = tempfile.NamedTemporaryFile(
        suffix=".json", prefix="aigc_demo_failed_", delete=False
    )
    tmp.write(json.dumps(_last_failed_artifact).encode())
    tmp.close()

    result = subprocess.run(
        [sys.executable, "-m", "aigc", "workflow", "doctor",
         tmp.name, "--json"],
        capture_output=True, text=True,
    )
    findings = (
        json.loads(result.stdout)
        if result.returncode == 0 and result.stdout.strip()
        else []
    )
    return {"findings": findings, "source": "last_failure_artifact"}
