"""Workflow timeline reconstruction from workflow and invocation artifacts."""
from __future__ import annotations

from typing import Any

from aigc._internal.audit import checksum as _checksum

TRACE_SCHEMA_VERSION = "0.9.0"


def reconstruct_trace(
    workflow_artifact: dict[str, Any],
    invocation_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Reconstruct a timeline for a single workflow artifact.

    Matches each step to its invocation artifact by SHA-256 checksum.
    Steps whose invocation artifact is absent are marked unresolved —
    typically indicating an audit sink failure or incomplete export.
    """
    inv_by_cs: dict[str, dict[str, Any]] = {
        _checksum(a): a for a in invocation_artifacts
    }

    steps: list[dict[str, Any]] = []
    for i, step in enumerate(workflow_artifact.get("steps", [])):
        cs = step.get("invocation_artifact_checksum")
        inv = inv_by_cs.get(cs) if cs else None
        steps.append({
            "sequence": i + 1,
            "step_id": step.get("step_id"),
            "participant_id": step.get("participant_id"),
            "invocation_artifact_checksum": cs,
            "resolved": inv is not None,
            "invocation_summary": _summarize(inv) if inv else None,
        })

    started = workflow_artifact.get("started_at")
    finalized = workflow_artifact.get("finalized_at")
    duration = (
        (finalized - started)
        if started is not None and finalized is not None
        else None
    )

    unresolved = [
        s["invocation_artifact_checksum"]
        for s in steps
        if not s["resolved"] and s["invocation_artifact_checksum"]
    ]

    return {
        "trace_schema_version": TRACE_SCHEMA_VERSION,
        "session_id": workflow_artifact.get("session_id"),
        "status": workflow_artifact.get("status"),
        "policy_file": workflow_artifact.get("policy_file"),
        "started_at": started,
        "finalized_at": finalized,
        "duration_seconds": duration,
        "step_count": len(steps),
        "steps": steps,
        "failure_summary": workflow_artifact.get("failure_summary"),
        "approval_checkpoints": workflow_artifact.get("approval_checkpoints", []),
        "validator_hook_evidence": workflow_artifact.get("validator_hook_evidence", []),
        "unresolved_checksums": unresolved,
    }


def _summarize(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "enforcement_result": artifact.get("enforcement_result"),
        "model_provider": artifact.get("model_provider"),
        "model_identifier": artifact.get("model_identifier"),
        "role": artifact.get("role"),
        "risk_score": artifact.get("risk_score"),
        "failures": artifact.get("failures", []),
        "timestamp": artifact.get("timestamp"),
    }
