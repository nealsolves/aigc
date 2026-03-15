"""
Custom EnforcementGate plugin interface.

Allows safe insertion of custom enforcement gates into the pipeline
with deterministic ordering. Custom gates may add failures and metadata
but cannot bypass core governance or remove prior failures.

Safety invariants:
- Custom gates run at defined insertion points (pre/post authorization)
- Failures are append-only: custom gates cannot suppress prior failures
- Core gate ordering is preserved
- Pre-action enforcement proof (gates_evaluated) is maintained
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Mapping

logger = logging.getLogger("aigc.gates")

# Supported insertion points for custom gates
INSERTION_PRE_AUTHORIZATION = "pre_authorization"
INSERTION_POST_AUTHORIZATION = "post_authorization"
INSERTION_PRE_OUTPUT = "pre_output"
INSERTION_POST_OUTPUT = "post_output"

VALID_INSERTION_POINTS = (
    INSERTION_PRE_AUTHORIZATION,
    INSERTION_POST_AUTHORIZATION,
    INSERTION_PRE_OUTPUT,
    INSERTION_POST_OUTPUT,
)


class GateResult:
    """Result from a custom gate execution.

    Custom gates return GateResult to report:
    - passed: whether the gate passed
    - failures: list of failure dicts (appended to pipeline failures)
    - metadata: dict of metadata (merged into audit artifact metadata)
    """

    __slots__ = ("passed", "failures", "metadata")

    def __init__(
        self,
        passed: bool = True,
        failures: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.passed = passed
        self.failures = failures or []
        self.metadata = metadata or {}


class EnforcementGate(abc.ABC):
    """Abstract base class for custom enforcement gates.

    Subclass and implement ``evaluate()`` to add custom governance logic.
    Register instances with the AIGC class or enforcement pipeline.

    Safety contract:
    - Gates receive a read-only view of invocation and policy
    - Gates return GateResult (they cannot raise to bypass governance)
    - Failures are append-only (cannot suppress prior failures)
    - Gates cannot modify the invocation or policy

    Usage::

        class ComplianceGate(EnforcementGate):
            name = "compliance_check"
            insertion_point = "post_authorization"

            def evaluate(self, invocation, policy, context):
                if not context.get("compliance_approved"):
                    return GateResult(
                        passed=False,
                        failures=[{"code": "COMPLIANCE",
                                   "message": "Not approved",
                                   "field": None}],
                    )
                return GateResult(passed=True)
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique gate identifier. Used in gates_evaluated list."""

    @property
    @abc.abstractmethod
    def insertion_point(self) -> str:
        """Where this gate runs in the pipeline.

        Must be one of VALID_INSERTION_POINTS.
        """

    @abc.abstractmethod
    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        """Execute the custom gate logic.

        :param invocation: Read-only invocation dict
        :param policy: Read-only effective policy dict
        :param context: Mutable pipeline context for passing data
        :return: GateResult indicating pass/fail with optional metadata
        """


def validate_gate(gate: EnforcementGate) -> None:
    """Validate a custom gate configuration.

    :raises ValueError: If gate has invalid name or insertion point
    """
    if not gate.name or not isinstance(gate.name, str):
        raise ValueError(f"Gate must have a non-empty string name, got: {gate.name!r}")

    if gate.insertion_point not in VALID_INSERTION_POINTS:
        raise ValueError(
            f"Gate '{gate.name}' has invalid insertion_point "
            f"'{gate.insertion_point}'; must be one of {VALID_INSERTION_POINTS}"
        )


def sort_gates(gates: list[EnforcementGate]) -> dict[str, list[EnforcementGate]]:
    """Sort gates by insertion point, preserving registration order within groups.

    :param gates: List of custom gates
    :return: Dict mapping insertion_point -> ordered list of gates
    """
    grouped: dict[str, list[EnforcementGate]] = {
        point: [] for point in VALID_INSERTION_POINTS
    }
    for gate in gates:
        validate_gate(gate)
        grouped[gate.insertion_point].append(gate)
    return grouped


def run_gates(
    gates: list[EnforcementGate],
    invocation: Mapping[str, Any],
    policy: Mapping[str, Any],
    pipeline_context: dict[str, Any],
    gates_evaluated: list[str],
    prior_failures: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run a list of custom gates and collect results.

    Failures are append-only: prior_failures are preserved.
    Custom gate exceptions are caught and converted to failures
    (gates cannot crash the pipeline).

    :param gates: Gates to run at this insertion point
    :param invocation: Current invocation
    :param policy: Effective policy
    :param pipeline_context: Shared pipeline context
    :param gates_evaluated: Running gates_evaluated list (mutated)
    :param prior_failures: Failures accumulated so far
    :return: (accumulated_failures, merged_metadata)
    """
    accumulated_failures = list(prior_failures)
    merged_metadata: dict[str, Any] = {}

    for gate in gates:
        gate_id = f"custom:{gate.name}"
        try:
            result = gate.evaluate(invocation, policy, pipeline_context)
        except Exception as exc:  # noqa: BLE001
            logger.error("Custom gate '%s' raised: %s", gate.name, exc)
            result = GateResult(
                passed=False,
                failures=[{
                    "code": "CUSTOM_GATE_ERROR",
                    "message": f"Gate '{gate.name}' raised: {exc}",
                    "field": None,
                }],
            )

        gates_evaluated.append(gate_id)

        if result.failures:
            accumulated_failures.extend(result.failures)
        if result.metadata:
            merged_metadata.update(result.metadata)

        logger.debug(
            "Custom gate '%s' completed: passed=%s, failures=%d",
            gate.name,
            result.passed,
            len(result.failures),
        )

    return accumulated_failures, merged_metadata
