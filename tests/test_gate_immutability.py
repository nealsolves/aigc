"""Tests proving custom gates cannot mutate policy or invocation objects.

Validates that _ImmutableView blocks all mutation operations and that
run_gates() converts mutation attempts into CUSTOM_GATE_MUTATION failures.
"""
import pytest
from typing import Any, Mapping

from aigc._internal.gates import (
    EnforcementGate,
    GateResult,
    run_gates,
    INSERTION_POST_AUTHORIZATION,
    _ImmutableView,
)
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import GovernanceViolationError


# ── _ImmutableView unit tests ────────────────────────────────────


class TestImmutableViewBlocksMutation:
    """_ImmutableView must raise TypeError with 'read-only' on mutation."""

    def setup_method(self):
        self.view = _ImmutableView({"key": "value", "other": 42})

    def test_setitem_blocked(self):
        with pytest.raises(TypeError, match="read-only"):
            self.view["key"] = "new"

    def test_delitem_blocked(self):
        with pytest.raises(TypeError, match="read-only"):
            del self.view["key"]

    def test_pop_blocked(self):
        with pytest.raises(TypeError, match="read-only"):
            self.view.pop("key")

    def test_update_blocked(self):
        with pytest.raises(TypeError, match="read-only"):
            self.view.update({"key": "new"})

    def test_clear_blocked(self):
        with pytest.raises(TypeError, match="read-only"):
            self.view.clear()

    def test_read_access_works(self):
        """Reads must succeed even though mutations are blocked."""
        assert self.view["key"] == "value"
        assert self.view["other"] == 42
        assert len(self.view) == 2
        assert "key" in self.view


class TestImmutableViewRecursiveWrapping:
    """Nested dicts must also be wrapped as _ImmutableView."""

    def test_nested_dict_is_immutable(self):
        view = _ImmutableView({"outer": {"inner": "val"}})
        nested = view["outer"]
        assert isinstance(nested, _ImmutableView)
        assert nested["inner"] == "val"

    def test_nested_dict_setitem_blocked(self):
        view = _ImmutableView({"outer": {"inner": "val"}})
        nested = view["outer"]
        with pytest.raises(TypeError, match="read-only"):
            nested["inner"] = "mutated"

    def test_nested_dict_delitem_blocked(self):
        view = _ImmutableView({"outer": {"inner": "val"}})
        nested = view["outer"]
        with pytest.raises(TypeError, match="read-only"):
            del nested["inner"]

    def test_deeply_nested_dict_is_immutable(self):
        view = _ImmutableView({"a": {"b": {"c": "deep"}}})
        deep = view["a"]["b"]
        assert isinstance(deep, _ImmutableView)
        assert deep["c"] == "deep"
        with pytest.raises(TypeError, match="read-only"):
            deep["c"] = "mutated"


class TestImmutableViewListConversion:
    """Nested lists must be converted to tuples."""

    def test_list_becomes_tuple(self):
        view = _ImmutableView({"items": [1, 2, 3]})
        result = view["items"]
        assert isinstance(result, tuple)
        assert result == (1, 2, 3)

    def test_list_of_dicts_becomes_tuple_of_immutable_views(self):
        view = _ImmutableView({"items": [{"a": 1}, {"b": 2}]})
        result = view["items"]
        assert isinstance(result, tuple)
        assert isinstance(result[0], _ImmutableView)
        assert result[0]["a"] == 1
        with pytest.raises(TypeError, match="read-only"):
            result[0]["a"] = 99

    def test_tuple_is_not_appendable(self):
        view = _ImmutableView({"items": [1, 2]})
        result = view["items"]
        with pytest.raises(AttributeError):
            result.append(3)


# ── Mutating gate implementations ────────────────────────────────


class PolicyMutatingGate(EnforcementGate):
    """Gate that attempts to mutate policy['roles']."""

    @property
    def name(self):
        return "policy_mutator"

    @property
    def insertion_point(self):
        return INSERTION_POST_AUTHORIZATION

    def evaluate(self, invocation, policy, context):
        policy["roles"] = ["hacked"]
        return GateResult(passed=True)


class InvocationMutatingGate(EnforcementGate):
    """Gate that attempts to mutate invocation['context']."""

    @property
    def name(self):
        return "invocation_mutator"

    @property
    def insertion_point(self):
        return INSERTION_POST_AUTHORIZATION

    def evaluate(self, invocation, policy, context):
        invocation["context"] = {"injected": True}
        return GateResult(passed=True)


class NestedPolicyMutatingGate(EnforcementGate):
    """Gate that attempts to mutate policy at a nested level."""

    @property
    def name(self):
        return "nested_policy_mutator"

    @property
    def insertion_point(self):
        return INSERTION_POST_AUTHORIZATION

    def evaluate(self, invocation, policy, context):
        nested = policy["preconditions"]
        nested["injected_condition"] = True
        return GateResult(passed=True)


# ── run_gates mutation detection ─────────────────────────────────


class TestRunGatesMutationDetection:
    """run_gates must convert mutation TypeError into CUSTOM_GATE_MUTATION."""

    def test_policy_mutation_produces_failure(self):
        gates_evaluated = []
        failures, _ = run_gates(
            [PolicyMutatingGate()],
            {},
            {"roles": ["planner"]},
            {},
            gates_evaluated,
            [],
        )
        assert len(failures) == 1
        assert failures[0]["code"] == "CUSTOM_GATE_MUTATION"
        assert "policy_mutator" in failures[0]["message"]
        assert "custom:policy_mutator" in gates_evaluated

    def test_invocation_mutation_produces_failure(self):
        gates_evaluated = []
        failures, _ = run_gates(
            [InvocationMutatingGate()],
            {"context": {"role_declared": True}},
            {},
            {},
            gates_evaluated,
            [],
        )
        assert len(failures) == 1
        assert failures[0]["code"] == "CUSTOM_GATE_MUTATION"
        assert "invocation_mutator" in failures[0]["message"]
        assert "custom:invocation_mutator" in gates_evaluated

    def test_nested_policy_mutation_produces_failure(self):
        gates_evaluated = []
        failures, _ = run_gates(
            [NestedPolicyMutatingGate()],
            {},
            {"preconditions": {"role_declared": True}},
            {},
            gates_evaluated,
            [],
        )
        assert len(failures) == 1
        assert failures[0]["code"] == "CUSTOM_GATE_MUTATION"
        assert "nested_policy_mutator" in failures[0]["message"]

    def test_original_data_unchanged_after_mutation_attempt(self):
        """The underlying dicts must remain untouched after a gate tries
        to mutate the immutable view."""
        original_policy = {"roles": ["planner"]}
        original_invocation = {"context": {"role_declared": True}}
        run_gates(
            [PolicyMutatingGate()],
            dict(original_invocation),
            dict(original_policy),
            {},
            [],
            [],
        )
        assert original_policy == {"roles": ["planner"]}
        assert original_invocation == {"context": {"role_declared": True}}


# ── Integration: AIGC with a mutating gate ───────────────────────


VALID_INVOCATION = {
    "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "planner",
    "input": {"prompt": "test"},
    "output": {"result": "ok", "confidence": 0.9},
    "context": {"role_declared": True, "schema_exists": True},
}


def test_aigc_mutating_gate_produces_governance_failure():
    """AIGC with a mutating gate must produce a FAIL enforcement result."""
    aigc = AIGC(custom_gates=[PolicyMutatingGate()])
    with pytest.raises(GovernanceViolationError) as exc_info:
        aigc.enforce(VALID_INVOCATION)
    exc = exc_info.value
    artifact = exc.audit_artifact
    assert artifact is not None
    assert artifact["enforcement_result"] == "FAIL"
    assert artifact["failure_gate"] == "custom_gate_violation"
    # The CUSTOM_GATE_MUTATION code is preserved in the exception details
    assert "custom_gate_failures" in exc.details
    detail_codes = [f["code"] for f in exc.details["custom_gate_failures"]]
    assert "CUSTOM_GATE_MUTATION" in detail_codes
    # The mutation message surfaces in the artifact failure message
    assert "mutate read-only data" in artifact["failures"][0]["message"]
