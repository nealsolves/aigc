"""
v0.9.0 workflow governance demo routes.

Uses real AIGC.open_session() — no fake backend behavior.
All imports are from the public aigc API only (no aigc._internal).
"""
from __future__ import annotations

import atexit
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import aigc.presets as presets
from aigc import AIGC, JsonFileAuditSink

router = APIRouter(prefix="/api/workflow/v090", tags=["workflow-v090"])

# Per-run state keyed by run_id returned from the failure scenario.
# Bounded to prevent unbounded temp-dir growth; evicted entries are cleaned up.
_MAX_RUNS = 20
# run_id -> {"starter_dir": str, "artifact": dict, "original_source": str}
_run_state: dict[str, dict] = {}
_POLICY_TMPDIR = tempfile.TemporaryDirectory(prefix="aigc_demo_policies_")
_policy_cache: dict[str, str] = {}


def _store_run(starter_dir: str, artifact: dict, original_source: str) -> str:
    """Store per-run failure state; return a new opaque run_id."""
    run_id = uuid.uuid4().hex
    if len(_run_state) >= _MAX_RUNS:
        oldest_id = next(iter(_run_state))
        old = _run_state.pop(oldest_id)
        shutil.rmtree(old["starter_dir"], ignore_errors=True)
    _run_state[run_id] = {
        "starter_dir": starter_dir,
        "artifact": artifact,
        "original_source": original_source,
    }
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


def _generate_starter_dir(profile: str) -> str:
    starter_dir = tempfile.mkdtemp(
        prefix=f"aigc_demo_{profile}_",
        dir=_POLICY_TMPDIR.name,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "aigc",
            "workflow",
            "init",
            "--profile",
            profile,
            "--output-dir",
            starter_dir,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"starter generation failed for {profile}: {result.stderr or result.stdout}"
        )
    return starter_dir


def _load_workflow_module(starter_dir: str):
    workflow_py = Path(starter_dir) / "workflow_example.py"
    module_name = f"_aigc_demo_workflow_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, workflow_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load workflow module from {workflow_py}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_workflow_module(starter_dir: str, func_name: str) -> tuple[dict | None, str | None]:
    mod = _load_workflow_module(starter_dir)
    try:
        artifact = getattr(mod, func_name)()
        return artifact, None
    except Exception as exc:  # noqa: BLE001
        return getattr(mod, "LAST_WORKFLOW_ARTIFACT", None), str(exc)


def _break_regulated_starter(starter_dir: str) -> str:
    workflow_py = Path(starter_dir) / "workflow_example.py"
    original_source = workflow_py.read_text(encoding="utf-8")
    broken_source = original_source.replace(
        '                    "source_ids": ["doc-001", "doc-002"],\n',
        "",
    ).replace(
        '                    "source_ids": ["analysis-step-1"],\n',
        "",
    )
    if broken_source == original_source:
        raise RuntimeError("could not apply regulated starter failure edit")
    workflow_py.write_text(broken_source, encoding="utf-8")
    return original_source


class WorkflowRunRequest(BaseModel):
    scenario: Literal["minimal", "standard", "failure", "regulated"]
    run_id: str | None = None


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
        if req.run_id is not None and req.run_id in _run_state:
            run = _run_state[req.run_id]
            starter_dir = run["starter_dir"]
            (Path(starter_dir) / "workflow_example.py").write_text(
                run["original_source"],
                encoding="utf-8",
            )
            artifact, error = _run_workflow_module(
                starter_dir,
                "run_regulated_workflow",
            )
            run["artifact"] = artifact or {}
            return {"artifact": artifact, "error": error, "run_id": req.run_id}

        starter_dir = _generate_starter_dir("regulated-high-assurance")
        artifact, error = _run_workflow_module(starter_dir, "run_regulated_workflow")
        return {"artifact": artifact, "error": error}

    else:  # failure
        starter_dir = _generate_starter_dir("regulated-high-assurance")
        original_source = _break_regulated_starter(starter_dir)
        artifact, error = _run_workflow_module(starter_dir, "run_regulated_workflow")
        run_id = _store_run(starter_dir, artifact or {}, original_source)
        return {"artifact": artifact, "error": error, "run_id": run_id}


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


@router.get("/trace")
def trace_evidence():
    """Run a governed 2-step minimal session with a JSONL sink and return the workflow trace.

    Implements the evidence view: produces real workflow + invocation artifacts,
    writes them to a temp JSONL file via JsonFileAuditSink, then reconstructs the
    timeline via 'aigc workflow trace'. No fake backend behavior.
    """
    policy_file = _get_policy_path("minimal")
    jsonl_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, dir=_POLICY_TMPDIR.name
    )
    jsonl_path = jsonl_file.name
    jsonl_file.close()

    sink = JsonFileAuditSink(jsonl_path)
    governance = AIGC(sink=sink)
    prompts = ["Analyze the document.", "Summarize the findings."]
    with governance.open_session(policy_file=policy_file) as session:
        for prompt in prompts:
            pre = session.enforce_step_pre_call({
                "policy_file": policy_file,
                "input": {"prompt": prompt},
                "output": {},
                "context": {"caller_id": "demo-evidence"},
                "model_provider": "anthropic",
                "model_identifier": "claude-sonnet-4-6",
                "role": "ai-assistant",
            })
            session.enforce_step_post_call(pre, {"result": f"Response to: {prompt[:60]}"})
        session.complete()

    result = subprocess.run(
        [sys.executable, "-m", "aigc", "workflow", "trace", "--input", jsonl_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"workflow trace failed: {result.stderr.strip() or '(no stderr)'}",
        )
    try:
        traces = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="workflow trace returned non-JSON output",
        )
    return {"traces": traces, "artifact": session.workflow_artifact}
