"""
Generates structured audit artifacts for model invocations.

These artifacts must be stored/consumed by the system
to support:
- replay
- audit
- compliance analysis
"""

from __future__ import annotations

import time
import hashlib
from typing import Any, Dict, Iterable, Mapping

from src.utils import canonical_json_bytes


POLICY_SCHEMA_VERSION = "http://json-schema.org/draft-07/schema#"
AUDIT_SCHEMA_VERSION = "1.1"


def checksum(obj: Mapping[str, Any]) -> str:
    """
    Generate checksum from canonical JSON bytes.

    :param obj: JSON-serializable mapping representing input or output
    """
    data = canonical_json_bytes(obj)
    return hashlib.sha256(data).hexdigest()


def _normalize_failures(
    failures: Iterable[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not failures:
        return []
    normalized: list[dict[str, Any]] = []
    for failure in failures:
        normalized.append(
            {
                "code": str(failure.get("code", "UNKNOWN")),
                "message": str(failure.get("message", "")),
                "field": (
                    str(failure.get("field"))
                    if failure.get("field") is not None
                    else None
                ),
            }
        )
    return sorted(normalized, key=canonical_json_bytes)


def generate_audit_artifact(
    invocation: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    enforcement_result: str = "PASS",
    failures: Iterable[Mapping[str, Any]] | None = None,
    failure_gate: str | None = None,
    failure_reason: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    timestamp: int | None = None,
) -> Dict[str, Any]:
    """
    Gather required audit fields and return structured object.

    :param invocation: original invocation data
    :param policy: loaded policy definitions
    :param enforcement_result: PASS/FAIL
    :param failures: structured failure list
    :param failure_gate: which enforcement gate failed (for FAIL results)
    :param failure_reason: human-readable failure reason (for FAIL results)
    :param metadata: additional enforcement metadata
    :param timestamp: optional explicit epoch timestamp for deterministic tests
    :return: audit artifact
    """
    failure_list = _normalize_failures(failures)
    metadata_dict = dict(metadata or {})

    return {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "policy_file": invocation["policy_file"],
        "policy_schema_version": POLICY_SCHEMA_VERSION,
        "policy_version": policy.get("policy_version"),
        "model_provider": invocation["model_provider"],
        "model_identifier": invocation["model_identifier"],
        "role": invocation["role"],
        "enforcement_result": enforcement_result,
        "failures": failure_list,
        "failure_gate": failure_gate,
        "failure_reason": failure_reason,
        "input_checksum": checksum(invocation["input"]),
        "output_checksum": checksum(invocation["output"]),
        "context": dict(invocation.get("context") or {}),
        "timestamp": int(time.time()) if timestamp is None else int(timestamp),
        "metadata": metadata_dict,
    }
