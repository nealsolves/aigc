"""
Built-in ProvenanceGate: enforce source presence before output.

ProvenanceGate is the first workflow-aware built-in enforcement gate.
It runs at INSERTION_PRE_OUTPUT and blocks invocations whose runtime
context lacks provenance source identifiers.

Pass provenance in the invocation context::

    invocation = {
        ...
        "context": {
            "provenance": {
                "source_ids": ["step-1"],
            },
        },
    }
    aigc = AIGC(custom_gates=[ProvenanceGate()])

Failure codes:

- ``PROVENANCE_MISSING``: no provenance key in invocation context, the
  value is None / empty, or the value is not a Mapping.
- ``SOURCE_IDS_MISSING``: provenance is a valid Mapping but ``source_ids``
  is absent, empty, or not a list/tuple.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aigc._internal.gates import EnforcementGate, GateResult, INSERTION_PRE_OUTPUT

PROVENANCE_MISSING = "PROVENANCE_MISSING"
SOURCE_IDS_MISSING = "SOURCE_IDS_MISSING"


class ProvenanceGate(EnforcementGate):
    """Enforce source presence before accepting model output.

    Blocks invocations whose runtime context has no provenance or no
    ``source_ids``. Register alongside other custom gates::

        from aigc import AIGC, ProvenanceGate
        aigc = AIGC(custom_gates=[ProvenanceGate()])

    :param require_source_ids: When True (default) the gate fails unless
        ``invocation["context"]["provenance"]["source_ids"]`` contains at
        least one entry. Set to False to disable enforcement (useful in
        test stubs or migration).
    """

    def __init__(self, *, require_source_ids: bool = True) -> None:
        self._require_source_ids = require_source_ids

    @property
    def name(self) -> str:
        return "provenance_gate"

    @property
    def insertion_point(self) -> str:
        return INSERTION_PRE_OUTPUT

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        if not self._require_source_ids:
            return GateResult(passed=True)

        ctx = invocation.get("context") or {}
        provenance = ctx.get("provenance")

        # Must be a non-empty Mapping (scalar, None, or empty dict → missing)
        if not isinstance(provenance, Mapping) or not provenance:
            return GateResult(
                passed=False,
                failures=[{
                    "code": PROVENANCE_MISSING,
                    "message": (
                        "ProvenanceGate: no provenance in invocation context; "
                        "output requires source attribution"
                    ),
                    "field": "context.provenance",
                }],
            )

        source_ids = provenance.get("source_ids")
        # Must be a non-empty list or tuple (string "step-1" is not valid)
        if not isinstance(source_ids, (list, tuple)) or not source_ids:
            return GateResult(
                passed=False,
                failures=[{
                    "code": SOURCE_IDS_MISSING,
                    "message": (
                        "ProvenanceGate: provenance has no source_ids; "
                        "output requires at least one source identifier"
                    ),
                    "field": "context.provenance.source_ids",
                }],
            )

        return GateResult(passed=True)
