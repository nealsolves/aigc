"""Workflow export in operator and audit modes."""
from __future__ import annotations

import time
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
        for i, step in enumerate(wa.get("steps", [])):
            if not isinstance(step, dict):
                raise ValueError(
                    f"Corrupt workflow artifact at index {wa_idx}: steps[{i}] is not an object "
                    f"(type={type(step).__name__!r}). "
                    f"Run 'aigc workflow lint' to diagnose."
                )

    inv_by_cs: dict[str, dict[str, Any]] = {_checksum(a): a for a in invocation_artifacts}

    expected: set[str] = set()
    for wa in workflow_artifacts:
        expected.update(wa.get("invocation_audit_checksums", []))
    unresolved = sorted(expected - set(inv_by_cs.keys()))

    if mode == "operator":
        return _build_operator(workflow_artifacts, inv_by_cs, unresolved)
    return _build_audit(workflow_artifacts, inv_by_cs, unresolved)


def _build_operator(
    workflow_artifacts: list[dict[str, Any]],
    inv_by_cs: dict[str, dict[str, Any]],
    unresolved: list[str],
) -> dict[str, Any]:
    sessions = []
    for wa in workflow_artifacts:
        enriched = []
        for step in wa.get("steps", []):
            cs = step.get("invocation_artifact_checksum")
            enriched.append({**step, "invocation_artifact": inv_by_cs.get(cs) if cs else None})
        sessions.append({**wa, "steps": enriched})
    return {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "export_mode": "operator",
        "generated_at": int(time.time()),
        "sessions": sessions,
        "integrity": {
            "total_workflow_artifacts": len(workflow_artifacts),
            "total_invocation_artifacts": len(inv_by_cs),
            "unresolved_invocation_checksums": unresolved,
            "unresolved_count": len(unresolved),
            "verification_guidance": _OPERATOR_GUIDANCE,
        },
    }


def _build_audit(
    workflow_artifacts: list[dict[str, Any]],
    inv_by_cs: dict[str, dict[str, Any]],
    unresolved: list[str],
) -> dict[str, Any]:
    counts: dict[str, int] = {"COMPLETED": 0, "FAILED": 0, "CANCELED": 0, "INCOMPLETE": 0}
    sessions = []
    for wa in workflow_artifacts:
        status = wa.get("status", "INCOMPLETE")
        counts[status] = counts.get(status, 0) + 1
        step_summaries = []
        for step in wa.get("steps", []):
            cs = step.get("invocation_artifact_checksum")
            inv = inv_by_cs.get(cs) if cs else None
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
