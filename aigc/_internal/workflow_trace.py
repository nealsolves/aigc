"""Workflow timeline reconstruction from workflow and invocation artifacts."""
from __future__ import annotations

from collections import Counter
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
    inv_by_cs: dict[str, dict[str, Any]] = {_checksum(a): a for a in invocation_artifacts}
    available: Counter[str] = Counter(_checksum(a) for a in invocation_artifacts)

    if "steps" not in workflow_artifact:
        raw_steps: list[dict[str, Any]] = []
    else:
        _steps_field = workflow_artifact["steps"]
        if not isinstance(_steps_field, list):
            raise ValueError(
                "Corrupt workflow artifact: 'steps' must be a list, "
                f"got {type(_steps_field).__name__!r}. "
                "Run 'aigc workflow lint' to diagnose."
            )
        raw_steps = _steps_field
    for i, step in enumerate(raw_steps):
        if not isinstance(step, dict):
            raise ValueError(
                f"Corrupt workflow artifact: steps[{i}] is not an object "
                f"(type={type(step).__name__!r}). "
                f"Run 'aigc workflow lint' to diagnose."
            )

    # Consume one available artifact per step so duplicate-checksum steps are
    # counted individually — a second step for the same checksum is unresolved
    # when only one matching artifact is present.
    remaining = Counter(available)
    steps: list[dict[str, Any]] = []
    for i, step in enumerate(raw_steps):
        cs = step.get("invocation_artifact_checksum")
        resolved = bool(cs and remaining[cs] > 0)
        if resolved:
            remaining[cs] -= 1
        steps.append({
            "sequence": i + 1,
            "step_id": step.get("step_id"),
            "participant_id": step.get("participant_id"),
            "invocation_artifact_checksum": cs,
            "resolved": resolved,
            "invocation_summary": _summarize(inv_by_cs[cs]) if resolved else None,
        })

    started = workflow_artifact.get("started_at")
    finalized = workflow_artifact.get("finalized_at")
    if started is not None and (isinstance(started, bool) or not isinstance(started, (int, float))):
        raise ValueError(
            f"Corrupt workflow artifact: started_at must be numeric, "
            f"got {type(started).__name__!r}. "
            f"Run 'aigc workflow lint' to diagnose."
        )
    if finalized is not None and (
        isinstance(finalized, bool) or not isinstance(finalized, (int, float))
    ):
        raise ValueError(
            f"Corrupt workflow artifact: finalized_at must be numeric, "
            f"got {type(finalized).__name__!r}. "
            f"Run 'aigc workflow lint' to diagnose."
        )
    duration = (
        (finalized - started)
        if started is not None and finalized is not None
        else None
    )

    # Expected checksums: for each unique checksum, take the max count from
    # invocation_audit_checksums and per-step references so the unresolved set
    # is correct even when those two sources diverge.
    if "invocation_audit_checksums" not in workflow_artifact:
        _iac: list[Any] = []
    else:
        _iac_field = workflow_artifact["invocation_audit_checksums"]
        if not isinstance(_iac_field, list):
            raise ValueError(
                "Corrupt workflow artifact: 'invocation_audit_checksums' must be a list, "
                f"got {type(_iac_field).__name__!r}. "
                "Run 'aigc workflow lint' to diagnose."
            )
        _iac = _iac_field
    summary_counts: Counter[str] = Counter(cs for cs in _iac if cs)
    step_counts: Counter[str] = Counter(
        step.get("invocation_artifact_checksum")
        for step in raw_steps
        if step.get("invocation_artifact_checksum")
    )
    expected: Counter[str] = Counter()
    for cs in set(summary_counts) | set(step_counts):
        expected[cs] = max(summary_counts[cs], step_counts[cs])

    unresolved = sorted(
        cs
        for cs, exp_count in expected.items()
        for _ in range(max(0, exp_count - available[cs]))
    )

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
