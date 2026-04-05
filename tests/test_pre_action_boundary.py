"""Sentinel tests for pipeline ordering contract.

These tests enforce that authorization gates (guards, role, preconditions,
tool constraints) always run before output-processing gates (schema,
postconditions).  If a refactor changes gate order, renames gate IDs,
or drops gates_evaluated tracking, these tests will fail.

See: PIPELINE_CONTRACT comment in aigc/_internal/enforcement.py
"""

import pytest

from aigc._internal.enforcement import (
    AUTHORIZATION_GATES,
    GATE_GUARDS,
    GATE_POSTCONDS,
    GATE_PRECONDS,
    GATE_ROLE,
    GATE_SCHEMA,
    GATE_TOOLS,
    OUTPUT_GATES,
    enforce_invocation,
    enforce_post_call,
    enforce_pre_call,
)
from aigc._internal.errors import ToolConstraintViolationError


def _base_invocation(**overrides):
    """Minimal valid invocation with tool + schema that both pass."""
    inv = {
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4",
        "role": "planner",
        "policy_file": "tests/golden_replays/policy_with_tools.yaml",
        "input": {"task": "research topic"},
        "output": {"result": "research complete", "confidence": 0.92},
        "context": {"role_declared": True},
        "tool_calls": [
            {"name": "search_knowledge_base", "call_id": "tc-1"},
        ],
    }
    inv.update(overrides)
    return inv


class TestToolsBeforeSchema:
    """D-04 tripwire: tool constraint validation must run before schema."""

    def test_tool_failure_blocks_schema_gate(self):
        """When both tools and schema would fail, tools fail first."""
        invocation = _base_invocation(
            # Unauthorized tool → tool constraint violation
            tool_calls=[{"name": "dangerous_tool", "call_id": "tc-1"}],
            # Invalid output → schema would also fail (missing required fields)
            output={"unexpected_key": "bad"},
        )

        with pytest.raises(ToolConstraintViolationError) as exc_info:
            enforce_invocation(invocation)

        audit = exc_info.value.audit_artifact
        assert audit["enforcement_result"] == "FAIL"
        assert audit["failure_gate"] == "tool_validation"

        gates = audit["metadata"]["gates_evaluated"]
        # Tool gate failed, so it is NOT recorded (gates record completions).
        # The critical assertion: schema never ran because tools come first.
        assert GATE_SCHEMA not in gates, (
            "Schema gate must not run when tool constraint fails first"
        )

    def test_tool_gate_precedes_schema_gate_in_artifact(self):
        """gates_evaluated proves pipeline stopped at tools, before schema."""
        invocation = _base_invocation(
            tool_calls=[{"name": "dangerous_tool", "call_id": "tc-1"}],
            output={"unexpected_key": "bad"},
        )

        with pytest.raises(ToolConstraintViolationError) as exc_info:
            enforce_invocation(invocation)

        gates = exc_info.value.audit_artifact["metadata"]["gates_evaluated"]

        # Authorization gates that completed before the failure
        assert GATE_GUARDS in gates
        assert GATE_ROLE in gates
        assert GATE_PRECONDS in gates

        # Tool gate failed (not recorded), but no output gates ran either
        assert GATE_TOOLS not in gates, "Failed gate should not be recorded"
        for output_gate in OUTPUT_GATES:
            assert output_gate not in gates


class TestGatesEvaluatedOnPass:
    """Verify gates_evaluated is complete and correctly ordered on PASS."""

    def test_all_gates_present_on_pass(self):
        """A successful enforcement records all six gates."""
        invocation = _base_invocation()
        audit = enforce_invocation(invocation)

        gates = audit["metadata"]["gates_evaluated"]
        assert gates == [
            GATE_GUARDS,
            GATE_ROLE,
            GATE_PRECONDS,
            GATE_TOOLS,
            GATE_SCHEMA,
            GATE_POSTCONDS,
        ]

    def test_authorization_gates_before_output_gates(self):
        """All authorization gates appear before any output gate."""
        invocation = _base_invocation()
        audit = enforce_invocation(invocation)

        gates = audit["metadata"]["gates_evaluated"]
        for auth_gate in AUTHORIZATION_GATES:
            for out_gate in OUTPUT_GATES:
                assert gates.index(auth_gate) < gates.index(out_gate), (
                    f"{auth_gate} must precede {out_gate}"
                )


class TestGatesEvaluatedOnFail:
    """Verify gates_evaluated captures partial progress on FAIL."""

    def test_early_failure_records_partial_gates(self):
        """A role validation failure records only guards + role gates."""
        invocation = _base_invocation(role="attacker")

        with pytest.raises(Exception) as exc_info:
            enforce_invocation(invocation)

        gates = exc_info.value.audit_artifact["metadata"]["gates_evaluated"]
        assert GATE_GUARDS in gates
        # Role validation failed, so GATE_ROLE should NOT be in gates
        # (the gate is recorded after success, not before)
        assert GATE_ROLE not in gates
        assert GATE_PRECONDS not in gates
        assert GATE_TOOLS not in gates


class TestGateConstants:
    """Verify gate constants haven't been silently renamed."""

    def test_gate_ids_are_stable(self):
        assert GATE_GUARDS == "guard_evaluation"
        assert GATE_ROLE == "role_validation"
        assert GATE_PRECONDS == "precondition_validation"
        assert GATE_TOOLS == "tool_constraint_validation"
        assert GATE_SCHEMA == "schema_validation"
        assert GATE_POSTCONDS == "postcondition_validation"

    def test_authorization_gates_tuple(self):
        assert AUTHORIZATION_GATES == (
            GATE_GUARDS, GATE_ROLE, GATE_PRECONDS, GATE_TOOLS,
        )

    def test_output_gates_tuple(self):
        assert OUTPUT_GATES == (GATE_SCHEMA, GATE_POSTCONDS)


class TestSplitModeGateOrdering:
    """Verify that split mode preserves the gate ordering contract.

    Phase A gates (authorization) must all appear before Phase B gates
    (output) when the two gate lists are concatenated.
    """

    def _split_invocation(self, **overrides):
        inv = {
            "model_provider": "anthropic",
            "model_identifier": "claude-sonnet-4",
            "role": "planner",
            "policy_file": "tests/golden_replays/policy_with_tools.yaml",
            "input": {"task": "research topic"},
            "context": {"role_declared": True},
            "tool_calls": [
                {"name": "search_knowledge_base", "call_id": "tc-1"},
            ],
        }
        inv.update(overrides)
        return inv

    def test_split_mode_phase_a_before_phase_b(self):
        """In split mode, all Phase A gates precede all Phase B gates."""
        inv = self._split_invocation()
        pre = enforce_pre_call(inv)
        audit = enforce_post_call(
            pre, {"result": "research complete", "confidence": 0.92},
        )

        meta = audit["metadata"]
        pre_gates = meta["pre_call_gates_evaluated"]
        post_gates = meta["post_call_gates_evaluated"]

        # Every Phase A gate is an authorization gate
        for gate in pre_gates:
            assert gate in AUTHORIZATION_GATES, (
                f"Phase A gate {gate!r} is not an authorization gate"
            )

        # Every Phase B gate is an output gate
        for gate in post_gates:
            assert gate in OUTPUT_GATES, (
                f"Phase B gate {gate!r} is not an output gate"
            )

        # Concatenating them preserves auth-before-output ordering
        combined = pre_gates + post_gates
        for auth_gate in AUTHORIZATION_GATES:
            if auth_gate in combined:
                for out_gate in OUTPUT_GATES:
                    if out_gate in combined:
                        assert combined.index(auth_gate) < (
                            combined.index(out_gate)
                        ), (
                            f"{auth_gate} must precede {out_gate} "
                            "in split mode"
                        )
