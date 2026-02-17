"""
Shared deterministic serialization utilities.
"""

from __future__ import annotations

import json
from typing import Any


def canonical_json_bytes(obj: Any) -> bytes:
    """
    Serialize an object to canonical JSON bytes.

    Canonicalization rules:
    - UTF-8 encoding
    - deterministic key ordering
    - compact separators
    - non-ASCII preserved (ensure_ascii=False)
    - NaN/Infinity rejected (allow_nan=False)
    """
    canonical = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return canonical.encode("utf-8")
