"""
Generates structured audit artifacts for model invocations.

These artifacts must be stored/consumed by the system
to support:
- replay
- audit
- compliance analysis
"""

from __future__ import annotations

import logging
import re
import time
import hashlib
from typing import Any, Dict, Iterable, Mapping

from aigc._internal.utils import canonical_json_bytes

logger = logging.getLogger("aigc.audit")


POLICY_SCHEMA_VERSION = "http://json-schema.org/draft-07/schema#"
AUDIT_SCHEMA_VERSION = "1.2"

MAX_FAILURES = 1000
MAX_METADATA_KEYS = 100
MAX_CONTEXT_KEYS = 100

# Default redaction patterns for sensitive data in failure messages
DEFAULT_REDACTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key", re.compile(r"(?:sk|key|api[_-]?key)[_-][A-Za-z0-9]{16,}", re.IGNORECASE)),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE)),
    ("email", re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
]


def sanitize_failure_message(
    message: str,
    patterns: list[tuple[str, re.Pattern[str]]] | None = None,
) -> tuple[str, list[str]]:
    """
    Sanitize a failure message by redacting sensitive data.

    :param message: Raw failure message
    :param patterns: List of (pattern_name, compiled_regex) tuples.
                     Defaults to DEFAULT_REDACTION_PATTERNS.
    :return: Tuple of (sanitized_message, list of redacted pattern names)
    """
    if patterns is None:
        patterns = DEFAULT_REDACTION_PATTERNS

    redacted_fields: list[str] = []
    sanitized = message

    for name, pattern in patterns:
        if pattern.search(sanitized):
            sanitized = pattern.sub(f"[REDACTED:{name}]", sanitized)
            if name not in redacted_fields:
                redacted_fields.append(name)

    return sanitized, redacted_fields


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
    risk_score: float | None = None,
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
    :param risk_score: computed risk score (None if not scored)
    :return: audit artifact
    """
    failure_list = _normalize_failures(failures)
    if len(failure_list) > MAX_FAILURES:
        logger.warning(
            "Truncating failures from %d to %d", len(failure_list), MAX_FAILURES
        )
        failure_list = failure_list[:MAX_FAILURES]

    metadata_dict = dict(metadata or {})
    if len(metadata_dict) > MAX_METADATA_KEYS:
        logger.warning(
            "Truncating metadata from %d to %d keys",
            len(metadata_dict),
            MAX_METADATA_KEYS,
        )
        keys = list(metadata_dict.keys())[:MAX_METADATA_KEYS]
        metadata_dict = {k: metadata_dict[k] for k in keys}

    context_dict = dict(invocation.get("context") or {})
    if len(context_dict) > MAX_CONTEXT_KEYS:
        logger.warning(
            "Truncating context from %d to %d keys",
            len(context_dict),
            MAX_CONTEXT_KEYS,
        )
        keys = list(context_dict.keys())[:MAX_CONTEXT_KEYS]
        context_dict = {k: context_dict[k] for k in keys}

    return {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "policy_file": invocation["policy_file"],
        "policy_schema_version": POLICY_SCHEMA_VERSION,
        "policy_version": policy.get("policy_version") or "unknown",
        "model_provider": invocation["model_provider"],
        "model_identifier": invocation["model_identifier"],
        "role": invocation["role"],
        "enforcement_result": enforcement_result,
        "failures": failure_list,
        "failure_gate": failure_gate,
        "failure_reason": failure_reason,
        "input_checksum": checksum(invocation["input"]),
        "output_checksum": checksum(invocation["output"]),
        "context": context_dict,
        "timestamp": int(time.time()) if timestamp is None else int(timestamp),
        "metadata": metadata_dict,
        "risk_score": risk_score,
        "signature": None,
    }
