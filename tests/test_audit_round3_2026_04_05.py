"""Regression tests for AIGC Round 3 audit findings (2026-04-05).

Finding 1 — Phase B gate bypass via _phase_b_grouped_gates mutation
Finding 2 — Phase A evidence forgery via nested-dict mutation of
            _frozen_invocation_snapshot, _frozen_phase_a_metadata,
            resolved_conditions, or resolved_guards
"""
from __future__ import annotations

import pytest

from aigc._internal.enforcement import (
    AIGC,
    enforce_invocation,
    enforce_post_call,
    enforce_pre_call,
    enforce_pre_call_async,
)
from aigc._internal.errors import CustomGateViolationError
from aigc._internal.gates import EnforcementGate, GateResult

GOLDEN_POLICY = "tests/golden_replays/golden_policy_v1.yaml"

INSERTION_PRE_OUTPUT = "pre_output"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pre_call_inv(**overrides):
    inv = {
        "policy_file": GOLDEN_POLICY,
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4-5-20250929",
        "role": "planner",
        "input": {"query": "test"},
        "context": {"role_declared": True, "schema_exists": True},
    }
    inv.update(overrides)
    return inv


def _valid_output():
    return {"result": "ok", "confidence": 0.9}


class _AlwaysFailPreOutputGate(EnforcementGate):
    """Gate that always fails at pre_output — used to verify bypass protection."""

    @property
    def name(self):
        return "always_fail_pre_output"

    @property
    def insertion_point(self):
        return INSERTION_PRE_OUTPUT

    def evaluate(self, invocation, policy, context):
        return GateResult(
            passed=False,
            failures=[{
                "code": "BLOCKED",
                "message": "always blocked",
                "field": None,
            }],
        )


# ── Finding 1: _phase_b_grouped_gates mutation bypass ─────────────────────────


class TestFinding1PhaseB_GatesBypassPrevention:
    """Mutating _phase_b_grouped_gates after Phase A must not bypass Phase B gates.

    After the fix, _phase_b_grouped_gates is a MappingProxyType with tuple
    values.  Any attempt to replace a gate list (old attack vector) raises
    TypeError and Phase B still enforces the gates that were registered.
    """

    def test_module_gates_field_is_immutable(self):
        """_phase_b_grouped_gates cannot be replaced via key assignment."""
        pre = enforce_pre_call(
            _pre_call_inv(),
            custom_gates=[_AlwaysFailPreOutputGate()],
        )
        with pytest.raises(TypeError):
            pre._phase_b_grouped_gates[INSERTION_PRE_OUTPUT] = []

    def test_module_inner_list_is_tuple(self):
        """Inner gate collections are tuples, not mutable lists."""
        pre = enforce_pre_call(
            _pre_call_inv(),
            custom_gates=[_AlwaysFailPreOutputGate()],
        )
        gates_at = pre._phase_b_grouped_gates.get(INSERTION_PRE_OUTPUT, ())
        assert isinstance(gates_at, tuple), (
            f"Expected tuple, got {type(gates_at)}"
        )

    def test_module_gate_still_enforced_after_failed_mutation(self):
        """Phase B still raises CustomGateViolationError after attempted mutation."""
        pre = enforce_pre_call(
            _pre_call_inv(),
            custom_gates=[_AlwaysFailPreOutputGate()],
        )
        # Attempted mutation raises TypeError and the dict is unchanged.
        try:
            pre._phase_b_grouped_gates[INSERTION_PRE_OUTPUT] = []
        except TypeError:
            pass

        with pytest.raises(CustomGateViolationError):
            enforce_post_call(pre, _valid_output())

    def test_aigc_gates_field_is_immutable(self):
        """AIGC instance: _phase_b_grouped_gates cannot be replaced."""
        engine = AIGC(custom_gates=[_AlwaysFailPreOutputGate()])
        pre = engine.enforce_pre_call(_pre_call_inv())
        with pytest.raises(TypeError):
            pre._phase_b_grouped_gates[INSERTION_PRE_OUTPUT] = []

    def test_aigc_gate_still_enforced_after_failed_mutation(self):
        """AIGC: Phase B still enforces gates after attempted mutation."""
        engine = AIGC(custom_gates=[_AlwaysFailPreOutputGate()])
        pre = engine.enforce_pre_call(_pre_call_inv())
        try:
            pre._phase_b_grouped_gates[INSERTION_PRE_OUTPUT] = []
        except TypeError:
            pass

        with pytest.raises(CustomGateViolationError):
            engine.enforce_post_call(pre, _valid_output())

    @pytest.mark.asyncio
    async def test_async_gates_field_is_immutable(self):
        """Async path: _phase_b_grouped_gates is a MappingProxyType."""
        pre = await enforce_pre_call_async(
            _pre_call_inv(),
            custom_gates=[_AlwaysFailPreOutputGate()],
        )
        with pytest.raises(TypeError):
            pre._phase_b_grouped_gates[INSERTION_PRE_OUTPUT] = []

    @pytest.mark.asyncio
    async def test_async_gate_still_enforced_after_failed_mutation(self):
        """Async: Phase B still enforces gates after attempted mutation."""
        engine = AIGC(custom_gates=[_AlwaysFailPreOutputGate()])
        pre = await engine.enforce_pre_call_async(_pre_call_inv())
        try:
            pre._phase_b_grouped_gates[INSERTION_PRE_OUTPUT] = []
        except TypeError:
            pass

        with pytest.raises(CustomGateViolationError):
            engine.enforce_post_call(pre, _valid_output())


# ── Finding 2: Phase A evidence forgery prevention ────────────────────────────


class TestFinding2EvidenceForgeryPrevention:
    """Mutating Phase A state on the token after enforce_pre_call() must not
    affect Phase B artifacts.

    After the fix, Phase B reads exclusively from _frozen_evidence_bytes
    (immutable bytes).  Mutations to _frozen_invocation_snapshot,
    _frozen_phase_a_metadata, resolved_conditions, and resolved_guards
    are ignored.
    """

    def test_invocation_snapshot_mutation_does_not_forge_policy_file(self):
        """Mutating _frozen_invocation_snapshot['policy_file'] is ignored by Phase B."""
        pre = enforce_pre_call(_pre_call_inv())
        original_policy_file = pre._frozen_invocation_snapshot["policy_file"]
        pre._frozen_invocation_snapshot["policy_file"] = "tampered.yaml"

        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["policy_file"] == original_policy_file

    def test_invocation_snapshot_mutation_does_not_forge_role(self):
        """Mutating _frozen_invocation_snapshot['role'] is ignored by Phase B."""
        pre = enforce_pre_call(_pre_call_inv())
        original_role = pre._frozen_invocation_snapshot["role"]
        pre._frozen_invocation_snapshot["role"] = "tampered-role"

        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["role"] == original_role

    def test_phase_a_metadata_mutation_does_not_forge_gates_evaluated(self):
        """Mutating _frozen_phase_a_metadata['gates_evaluated'] is ignored by Phase B."""
        pre = enforce_pre_call(_pre_call_inv())
        original_gates = list(
            pre._frozen_phase_a_metadata.get("gates_evaluated", []),
        )
        pre._frozen_phase_a_metadata["gates_evaluated"] = ["forged_gate"]

        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["metadata"]["pre_call_gates_evaluated"] == original_gates

    def test_phase_a_metadata_mutation_does_not_forge_timestamp(self):
        """Mutating _frozen_phase_a_metadata['pre_call_timestamp'] is ignored."""
        pre = enforce_pre_call(_pre_call_inv())
        original_ts = pre._frozen_phase_a_metadata.get("pre_call_timestamp")
        pre._frozen_phase_a_metadata["pre_call_timestamp"] = 0

        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["metadata"]["pre_call_timestamp"] == original_ts

    def test_resolved_conditions_mutation_does_not_forge_artifact(self):
        """Mutating resolved_conditions (public field) is ignored by Phase B."""
        pre = enforce_pre_call(_pre_call_inv())
        original_conditions = dict(pre.resolved_conditions)
        pre.resolved_conditions["forged_condition"] = True  # type: ignore[index]

        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["metadata"]["conditions_resolved"] == original_conditions

    def test_aigc_invocation_snapshot_mutation_ignored(self):
        """AIGC path: _frozen_invocation_snapshot mutation is ignored by Phase B."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        original_role = pre._frozen_invocation_snapshot["role"]
        pre._frozen_invocation_snapshot["role"] = "tampered-role"

        artifact = engine.enforce_post_call(pre, _valid_output())
        assert artifact["role"] == original_role

    def test_aigc_resolved_conditions_mutation_ignored(self):
        """AIGC path: resolved_conditions mutation is ignored by Phase B."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        original_conditions = dict(pre.resolved_conditions)
        pre.resolved_conditions["forged"] = True  # type: ignore[index]

        artifact = engine.enforce_post_call(pre, _valid_output())
        assert artifact["metadata"]["conditions_resolved"] == original_conditions
