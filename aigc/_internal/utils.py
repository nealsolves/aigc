"""
Shared deterministic serialization utilities.
"""

from __future__ import annotations

import json
from typing import Any


def _normalize_for_json(obj: Any) -> Any:
    """Normalize Python values to survive a JavaScript JSON round-trip.

    JavaScript's JSON.stringify converts integer-valued floats (0.0, 1.0)
    to integers (0, 1).  When Python re-parses these it gets int, not
    float, producing different canonical bytes.  Normalizing here ensures
    both sides agree on the canonical form.
    """
    if isinstance(obj, float):
        if obj != obj:  # NaN — leave for allow_nan=False to reject
            return obj
        if obj.is_integer():
            return int(obj)
        return obj
    if isinstance(obj, dict):
        return {k: _normalize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize_for_json(v) for v in obj]
    return obj


def canonical_json_bytes(obj: Any) -> bytes:
    """
    Serialize an object to canonical JSON bytes.

    Canonicalization rules:
    - UTF-8 encoding
    - deterministic key ordering
    - compact separators
    - non-ASCII preserved (ensure_ascii=False)
    - NaN/Infinity rejected (allow_nan=False)
    - integer-valued floats normalized to ints (JS compatibility)
    """
    normalized = _normalize_for_json(obj)
    canonical = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return canonical.encode("utf-8")
