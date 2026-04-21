"""Workflow export in operator and audit modes."""
from __future__ import annotations

import time
from collections import Counter
from typing import Any

from aigc._internal.audit import checksum as _checksum

EXPORT_SCHEMA_VERSION = "0.9.0"

_OPERATOR_GUIDANCE = (
    "Verify each invocation_artifact_checksum against SHA-256(canonical-JSON) "
    "of the corresponding invocation artifact. "
    "Unresolved checksums indicate artifacts that did not reach the audit sink "
    "(possible sink failures or incomplete export). "
    "Use 'aigc workflow doctor' to diagnose individual artifacts."
)

_AUDIT_GUIDANCE = (
    "Cross-reference invocation_artifact_checksum values against the source "
    "audit JSONL to verify completeness. "
    "Unresolved checksums may indicate sink failures; "
    "investigate with 'aigc workflow doctor'."
)


def export_workflow(
    workflow_artifacts: list[dict[str, Any]],
    invocation_artifacts: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    """Produce an export document from workflow and invocation artifacts.

    Args:
        workflow_artifacts: Dicts with ``artifact_type == "workflow"``.
        invocation_artifacts: Invocation artifact dicts to correlate.
        mode: ``"operator"`` (full technical dump with embedded invocation
            artifacts) or ``"audit"`` (compliance-focused step summaries).

    Raises:
        ValueError: If *mode* is not ``"operator"`` or ``"audit"``.
    """
    if mode not in ("operator", "audit"):
        raise ValueError(f"Unknown export mode: {mode!r}. Use 'operator' or 'audit'.")

    for wa_idx, wa in enumerate(workflow_artifacts):
        status = wa.get("status", "INCOMPLETE")
        if not isinstance(status, str):
            raise ValueError(
                f"Corrupt workflow artifact at index {wa_idx}: status must be a string, "
                f"got {type(status).__name__!r}. "
                f"Run 'aigc workflow lint' to diagnose."
            )
        if "steps" in wa:
            _wa_steps = wa["steps"]
            if not isinstance(_wa_steps, list):
                raise ValueError(
                    f"Corrupt workflow artifact at index {wa_idx}: 'steps' must be a list, "
                    f"got {type(_wa_steps).__name__!r}. "
                    f"Run 'aigc workflow lint' to diagnose."
                )
            for i, step in enumerate(_wa_steps):
                if not isinstance(step, dict):
                    raise ValueError(
                        f"Corrupt workflow artifact at index {wa_idx}: steps[{i}] is not an object "
                        f"(type={type(step).__name__!r}). "
                        f"Run 'aigc workflow lint' to diagnose."
                    )
                _cs_val = step.get("invocation_artifact_checksum")
                if _cs_val is not None and not isinstance(_cs_val, str):
                    raise ValueError(
                        f"Corrupt workflow artifact at index {wa_idx}: "
                        f"steps[{i}].invocation_artifact_checksum must be a string or null, "
                        f"got {type(_cs_val).__name__!r}. "
                        f"Run 'aigc workflow lint' to diagnose."
                    )
        if "invocation_audit_checksums" in wa:
            _wa_iac = wa["invocation_audit_checksums"]
            if not isinstance(_wa_iac, list):
                raise ValueError(
                    f"Corrupt workflow artifact at index {wa_idx}: "
                    f"'invocation_audit_checksums' must be a list, "
                    f"got {type(_wa_iac).__name__!r}. "
                    f"Run 'aigc workflow lint' to diagnose."
                )
            for _j, _entry in enumerate(_wa_iac):
                if not isinstance(_entry, str):
                    raise ValueError(
                        f"Corrupt workflow artifact at index {wa_idx}: "
                        f"invocation_audit_checksums[{_j}] must be a string, "
                        f"got {type(_entry).__name__!r}. "
                        f"Run 'aigc workflow lint' to diagnose."
                    )
        _started = wa.get("started_at")
        if _started is not None and (
            isinstance(_started, bool) or not isinstance(_started, (int, float))
        ):
            raise ValueError(
                f"Corrupt workflow artifact at index {wa_idx}: "
                f"started_at must be numeric, got {type(_started).__name__!r}. "
                f"Run 'aigc workflow lint' to diagnose."
            )
        _finalized = wa.get("finalized_at")
        if _finalized is not None and (
            isinstance(_finalized, bool) or not isinstance(_finalized, (int, float))
        ):
            raise ValueError(
                f"Corrupt workflow artifact at index {wa_idx}: "
                f"finalized_at must be numeric, got {type(_finalized).__name__!r}. "
                f"Run 'aigc workflow lint' to diagnose."
            )

    inv_by_cs: dict[str, dict[str, Any]] = {_checksum(a): a for a in invocation_artifacts}
    available: Counter[str] = Counter(_checksum(a) for a in invocation_artifacts)

    # Expected checksums: sum contributions across sessions, using max(summary_count,
    # step_count) within each session to avoid double-counting divergent sources.
    # Summing across sessions matches the sink model — the sink writes one line per
    # emitted invocation artifact, so two sessions that both record the same checksum
    # each expect their own artifact in the sink.
    expected: Counter[str] = Counter()
    for wa in workflow_artifacts:
        s_counts: Counter[str] = Counter(
            cs for cs in wa.get("invocation_audit_checksums", []) if cs
        )
        st_counts: Counter[str] = Counter(
            step.get("invocation_artifact_checksum")
            for step in wa.get("steps", [])
            if step.get("invocation_artifact_checksum")
        )
        for cs in set(s_counts) | set(st_counts):
            expected[cs] += max(s_counts[cs], st_counts[cs])

    unresolved = sorted(
        cs
        for cs, exp_count in expected.items()
        for _ in range(max(0, exp_count - available[cs]))
    )

    if mode == "operator":
        return _build_operator(
            workflow_artifacts, inv_by_cs, available, unresolved, len(invocation_artifacts)
        )
    return _build_audit(workflow_artifacts, inv_by_cs, available, unresolved)


def _build_operator(
    workflow_artifacts: list[dict[str, Any]],
    inv_by_cs: dict[str, dict[str, Any]],
    available: Counter[str],
    unresolved: list[str],
    total_invocation_artifacts: int,
) -> dict[str, Any]:
    # Consume one artifact slot per step across all sessions so a second step
    # referencing the same checksum gets None when only one artifact is present.
    remaining = Counter(available)
    sessions = []
    for wa in workflow_artifacts:
        enriched = []
        for step in wa.get("steps", []):
            cs = step.get("invocation_artifact_checksum")
            if cs and remaining[cs] > 0:
                remaining[cs] -= 1
                inv = inv_by_cs.get(cs)
            else:
                inv = None
            enriched.append({**step, "invocation_artifact": inv})
        sessions.append({**wa, "steps": enriched})
    return {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "export_mode": "operator",
        "generated_at": int(time.time()),
        "sessions": sessions,
        "integrity": {
            "total_workflow_artifacts": len(workflow_artifacts),
            "total_invocation_artifacts": total_invocation_artifacts,
            "unresolved_invocation_checksums": unresolved,
            "unresolved_count": len(unresolved),
            "verification_guidance": _OPERATOR_GUIDANCE,
        },
    }


def _build_audit(
    workflow_artifacts: list[dict[str, Any]],
    inv_by_cs: dict[str, dict[str, Any]],
    available: Counter[str],
    unresolved: list[str],
) -> dict[str, Any]:
    remaining = Counter(available)
    counts: dict[str, int] = {"COMPLETED": 0, "FAILED": 0, "CANCELED": 0, "INCOMPLETE": 0}
    sessions = []
    for wa in workflow_artifacts:
        status = wa.get("status", "INCOMPLETE")
        if status not in counts:
            raise ValueError(
                f"Corrupt workflow artifact: unsupported status {status!r}. "
                "Expected one of COMPLETED, FAILED, CANCELED, INCOMPLETE. "
                "Run 'aigc workflow lint' to diagnose."
            )
        counts[status] += 1
        step_summaries = []
        for step in wa.get("steps", []):
            cs = step.get("invocation_artifact_checksum")
            if cs and remaining[cs] > 0:
                remaining[cs] -= 1
                inv = inv_by_cs.get(cs)
            else:
                inv = None
            step_summaries.append({
                "step_id": step.get("step_id"),
                "participant_id": step.get("participant_id"),
                "invocation_artifact_checksum": cs,
                "enforcement_result": inv.get("enforcement_result") if inv else None,
            })
        sessions.append({
            "session_id": wa.get("session_id"),
            "status": status,
            "policy_file": wa.get("policy_file"),
            "started_at": wa.get("started_at"),
            "finalized_at": wa.get("finalized_at"),
            "step_count": len(wa.get("steps", [])),
            "steps": step_summaries,
            "failure_summary": wa.get("failure_summary"),
            "approval_checkpoints": wa.get("approval_checkpoints", []),
        })
    return {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "export_mode": "audit",
        "generated_at": int(time.time()),
        "sessions": sessions,
        "compliance_summary": {"total_sessions": len(workflow_artifacts), **counts},
        "integrity": {
            "unresolved_invocation_checksums": unresolved,
            "unresolved_count": len(unresolved),
            "verification_guidance": _AUDIT_GUIDANCE,
        },
    }
