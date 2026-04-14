"""
Generates structured audit artifacts for model invocations.

These artifacts must be stored/consumed by the system
to support:
- replay
- audit
- compliance analysis
"""

from __future__ import annotations

import json
import logging
import re
import time
import hashlib
from typing import Any, Dict, Iterable, Mapping

from aigc._internal.utils import canonical_json_bytes

logger = logging.getLogger("aigc.audit")


POLICY_SCHEMA_VERSION = "http://json-schema.org/draft-07/schema#"
AUDIT_SCHEMA_VERSION = "1.4"

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


# Provenance fields that the audit schema (v1.4) requires to be JSON arrays.
# Scalars in these positions are dropped at normalization time to prevent
# emitting schema-invalid artifacts.
_PROVENANCE_LIST_FIELDS: frozenset[str] = frozenset(
    {"source_ids", "derived_from_audit_checksums"}
)

# All provenance fields declared in the audit schema (additionalProperties: false).
# Unknown keys are silently dropped so the emitted artifact stays schema-valid.
_PROVENANCE_KNOWN_FIELDS: frozenset[str] = _PROVENANCE_LIST_FIELDS | frozenset(
    {"compilation_source_hash"}
)

# SHA-256 hex pattern used to validate checksum-bearing provenance fields.
_HEX64_RE = re.compile(r"^[a-f0-9]{64}$")

# Schema maxItems for provenance list fields; lists are truncated with a warning.
_PROVENANCE_MAX_LIST_ITEMS = 1000


def _normalize_provenance(
    provenance: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Normalize a caller-supplied provenance mapping for artifact emission.

    Returns None when provenance is absent, empty, or all values are pruned.
    Returns a sparse dict of normalized, schema-safe values otherwise.

    Normalization rules:
    - Unknown keys are dropped (audit schema has additionalProperties: false).
    - None values are dropped.
    - Fields that must be JSON arrays (source_ids, derived_from_audit_checksums)
      are dropped when their value is a scalar; this prevents schema-invalid
      artifacts when callers supply unexpected types.
    - Items in source_ids must be non-empty strings; non-string or empty-string
      items are filtered out. Non-JSON-serializable items raise ValueError.
    - Items in derived_from_audit_checksums must match ^[a-f0-9]{64}$;
      non-matching items are filtered out. Non-JSON-serializable items raise.
    - Duplicate items in list fields are removed (first occurrence kept).
    - List fields are truncated to 1000 items (schema maxItems) with a warning.
    - A list field that becomes empty after filtering is dropped entirely.
    - compilation_source_hash must be a string matching ^[a-f0-9]{64}$;
      non-string or pattern-failing values are silently dropped.
      Non-JSON-serializable values raise ValueError.
    """
    if provenance is None:
        return None
    if not isinstance(provenance, Mapping):
        return None

    out: dict[str, Any] = {}
    for k, v in provenance.items():
        if k not in _PROVENANCE_KNOWN_FIELDS or v is None:
            continue
        if k in _PROVENANCE_LIST_FIELDS:
            if not isinstance(v, (list, tuple)):
                # Scalar where array required: drop.
                continue
            # Validate serializability of each item BEFORE type filtering
            # to preserve the ValueError contract for NaN, sets, etc.
            for item in v:
                try:
                    json.dumps(item, allow_nan=False)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"provenance[{k!r}] contains non-JSON-serializable item: {exc}"
                    ) from exc
            # Filter by type/content constraints.
            if k == "source_ids":
                items: list[str] = [s for s in v if isinstance(s, str) and s]
            else:  # derived_from_audit_checksums
                items = [
                    s for s in v
                    if isinstance(s, str) and _HEX64_RE.match(s)
                ]
            # Deduplicate preserving insertion order.
            seen: set[str] = set()
            deduped: list[str] = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    deduped.append(item)
            # Truncate to schema maxItems, warn if lossy.
            if len(deduped) > _PROVENANCE_MAX_LIST_ITEMS:
                logger.warning(
                    "provenance[%r] truncated from %d to %d items (schema maxItems)",
                    k,
                    len(deduped),
                    _PROVENANCE_MAX_LIST_ITEMS,
                )
                deduped = deduped[:_PROVENANCE_MAX_LIST_ITEMS]
            if not deduped:
                # Empty after filtering: drop field entirely.
                continue
            out[k] = deduped
        else:
            # compilation_source_hash: validate serializability first.
            try:
                json.dumps(v, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"provenance[{k!r}] contains non-JSON-serializable value: {exc}"
                ) from exc
            # Must be a 64-char lowercase hex string.
            if not isinstance(v, str) or not _HEX64_RE.match(v):
                continue
            out[k] = v

    if not out:
        return None
    try:
        # Round-trip through JSON to: (1) validate serializability with
        # allow_nan=False, and (2) coerce Python tuples → JSON arrays (lists),
        # since jsonschema treats tuple as non-array.
        normalized = json.loads(json.dumps(out, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"provenance contains non-JSON-serializable values: {exc}"
        ) from exc
    return normalized


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
    provenance: Mapping[str, Any] | None = None,
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
    :param provenance: optional provenance metadata (source_ids,
                       derived_from_audit_checksums, compilation_source_hash)
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

    try:
        normalized_provenance = _normalize_provenance(provenance)
    except ValueError:
        logger.warning(
            "provenance normalization failed (non-JSON-serializable data); "
            "emitting artifact with provenance=null to preserve audit invariant"
        )
        normalized_provenance = None

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
        "provenance": normalized_provenance,
    }
