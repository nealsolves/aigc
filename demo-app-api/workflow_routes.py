"""
v0.9.0 workflow governance demo routes.

Uses real AIGC.open_session() — no fake backend behavior.
All imports are from the public aigc API only (no aigc._internal).
"""
from __future__ import annotations

import atexit
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

import aigc.presets as presets
from aigc import AIGC, ProvenanceGate

router = APIRouter(prefix="/api/workflow/v090", tags=["workflow-v090"])

# Per-run state keyed by run_id returned from the failure scenario.
# Bounded to prevent unbounded temp-dir growth; evicted entries are cleaned up.
_MAX_RUNS = 20
_run_state: dict[str, dict] = {}   # run_id -> {"starter_dir": str, "artifact": dict}
_POLICY_TMPDIR = tempfile.TemporaryDirectory(prefix="aigc_demo_policies_")
_policy_cache: dict[str, str] = {}


def _store_run(starter_dir: str, artifact: dict) -> str:
    """Store per-run failure state; return a new opaque run_id."""
    run_id = uuid.uuid4().hex
    if len(_run_state) >= _MAX_RUNS:
        oldest_id = next(iter(_run_state))
        old = _run_state.pop(oldest_id)
        shutil.rmtree(old["starter_dir"], ignore_errors=True)
    _run_state[run_id] = {"starter_dir": starter_dir, "artifact": artifact}
    return run_id


def _cleanup_temp_artifacts() -> None:
    for run in _run_state.values():
        shutil.rmtree(run["starter_dir"], ignore_errors=True)
    _run_state.clear()
    _policy_cache.clear()
    _POLICY_TMPDIR.cleanup()


atexit.register(_cleanup_temp_artifacts)


def _get_policy_path(profile: str) -> str:
    """Write preset policy YAML to a managed temp dir, cache and return the path."""
    if profile in _policy_cache:
        return _policy_cache[profile]
    preset_map = {
        "minimal": presets.MinimalPreset,
        "standard": presets.StandardPreset,
        "regulated": presets.RegulatedHighAssurancePreset,
    }
    preset = preset_map[profile]()
    policy_path = Path(_POLICY_TMPDIR.name) / f"{profile}.yaml"
    policy_path.write_text(preset.policy_yaml, encoding="utf-8")
    _policy_cache[profile] = str(policy_path)
    return str(policy_path)


def _sim(prompt: str) -> dict:
    return {"result": f"Response to: {prompt[:60]}"}


class WorkflowRunRequest(BaseModel):
    scenario: Literal["minimal", "standard", "failure", "regulated"]


@router.post("/run")
def run_workflow(req: WorkflowRunRequest):
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
        starter_dir = tempfile.mkdtemp(
            prefix="aigc_demo_starter_",
            dir=_POLICY_TMPDIR.name,
        )
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
        run_id = _store_run(starter_dir, artifact)
        return {"artifact": artifact, "error": caught_error, "run_id": run_id}


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
def diagnose_last_failure(run_id: str | None = None):
    """Run aigc workflow doctor on the starter dir for a specific run.

    ``run_id`` is returned by POST /run when scenario='failure'.  When omitted
    the most recent failure is used (single-user convenience fallback).
    """
    if run_id is not None:
        run = _run_state.get(run_id)
    else:
        run = list(_run_state.values())[-1] if _run_state else None

    if run is None:
        return {"findings": [], "source": "no_prior_failure"}

    starter_dir = run["starter_dir"]
    # The doctor detects WORKFLOW_SOURCE_REQUIRED by scanning workflow_example.py
    # for ProvenanceGate(require_source_ids=True) — it needs a directory, not an
    # artifact file.  We created that directory when the failure scenario ran.
    result = subprocess.run(
        [sys.executable, "-m", "aigc", "workflow", "doctor",
         starter_dir, "--json"],
        capture_output=True, text=True,
    )
    # Parse findings regardless of exit code: doctor exits 1 for ERROR-severity
    # findings, which are exactly the ones we want to surface to the user.
    try:
        findings = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        findings = []
    return {"findings": findings, "source": "failure_starter_dir"}
