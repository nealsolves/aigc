"""Tests for custom EnforcementGate plugin interface (M2 feature)."""
import pytest
from typing import Any, Mapping

from aigc._internal.gates import (
    EnforcementGate,
    GateResult,
    validate_gate,
    sort_gates,
    run_gates,
    INSERTION_PRE_AUTHORIZATION,
    INSERTION_POST_AUTHORIZATION,
    INSERTION_PRE_OUTPUT,
    INSERTION_POST_OUTPUT,
    VALID_INSERTION_POINTS,
)
from aigc._internal.enforcement import AIGC, enforce_invocation, GATE_GUARDS
from aigc._internal.errors import CustomGateViolationError, GovernanceViolationError


# ── Test gate implementations ────────────────────────────────────


class PassingGate(EnforcementGate):
    @property
    def name(self):
        return "passing_gate"

    @property
    def insertion_point(self):
        return INSERTION_POST_AUTHORIZATION

    def evaluate(self, invocation, policy, context):
        return GateResult(passed=True, metadata={"custom": "data"})


class FailingGate(EnforcementGate):
    @property
    def name(self):
        return "failing_gate"

    @property
    def insertion_point(self):
        return INSERTION_POST_AUTHORIZATION

    def evaluate(self, invocation, policy, context):
        return GateResult(
            passed=False,
            failures=[{
                "code": "CUSTOM_FAIL",
                "message": "Custom gate failed",
                "field": None,
            }],
        )


class CrashingGate(EnforcementGate):
    @property
    def name(self):
        return "crashing_gate"

    @property
    def insertion_point(self):
        return INSERTION_POST_AUTHORIZATION

    def evaluate(self, invocation, policy, context):
        raise RuntimeError("Unexpected crash")


class PreAuthGate(EnforcementGate):
    @property
    def name(self):
        return "pre_auth_gate"

    @property
    def insertion_point(self):
        return INSERTION_PRE_AUTHORIZATION

    def evaluate(self, invocation, policy, context):
        return GateResult(passed=True)


class PostOutputGate(EnforcementGate):
    @property
    def name(self):
        return "post_output_gate"

    @property
    def insertion_point(self):
        return INSERTION_POST_OUTPUT

    def evaluate(self, invocation, policy, context):
        return GateResult(passed=True, metadata={"post_output": True})


# ── validate_gate ────────────────────────────────────────────────


def test_validate_valid_gate():
    validate_gate(PassingGate())  # Should not raise


def test_validate_invalid_insertion_point():
    class BadGate(EnforcementGate):
        @property
        def name(self):
            return "bad"

        @property
        def insertion_point(self):
            return "invalid_point"

        def evaluate(self, inv, pol, ctx):
            return GateResult()

    with pytest.raises(ValueError, match="invalid insertion_point"):
        validate_gate(BadGate())


# ── sort_gates ───────────────────────────────────────────────────


def test_sort_gates_by_insertion_point():
    gates = [PassingGate(), PreAuthGate(), PostOutputGate()]
    grouped = sort_gates(gates)
    assert len(grouped[INSERTION_PRE_AUTHORIZATION]) == 1
    assert len(grouped[INSERTION_POST_AUTHORIZATION]) == 1
    assert len(grouped[INSERTION_POST_OUTPUT]) == 1
    assert len(grouped[INSERTION_PRE_OUTPUT]) == 0


def test_sort_preserves_order():
    class G1(PassingGate):
        @property
        def name(self):
            return "g1"

    class G2(PassingGate):
        @property
        def name(self):
            return "g2"

    gates = [G1(), G2()]
    grouped = sort_gates(gates)
    names = [g.name for g in grouped[INSERTION_POST_AUTHORIZATION]]
    assert names == ["g1", "g2"]


# ── run_gates ────────────────────────────────────────────────────


def test_run_passing_gate():
    gates_evaluated = []
    failures, metadata = run_gates(
        [PassingGate()], {}, {}, {}, gates_evaluated, []
    )
    assert failures == []
    assert metadata.get("custom") == "data"
    assert "custom:passing_gate" in gates_evaluated


def test_run_failing_gate_appends_failures():
    gates_evaluated = []
    prior_failures = [{"code": "PRIOR", "message": "existing", "field": None}]
    failures, _ = run_gates(
        [FailingGate()], {}, {}, {}, gates_evaluated, prior_failures
    )
    assert len(failures) == 2  # prior + new
    assert failures[0]["code"] == "PRIOR"
    assert failures[1]["code"] == "CUSTOM_FAIL"


def test_run_crashing_gate_converts_to_failure():
    gates_evaluated = []
    failures, _ = run_gates(
        [CrashingGate()], {}, {}, {}, gates_evaluated, []
    )
    assert len(failures) == 1
    assert failures[0]["code"] == "CUSTOM_GATE_ERROR"
    assert "Unexpected crash" in failures[0]["message"]


def test_custom_gates_cannot_remove_prior_failures():
    """Custom gates can only append failures, never remove prior ones."""
    prior = [{"code": "X", "message": "y", "field": None}]
    failures, _ = run_gates(
        [PassingGate()], {}, {}, {}, [], list(prior)
    )
    assert len(failures) >= len(prior)
    assert prior[0] in failures


# ── Integration with AIGC class ──────────────────────────────────


VALID_INVOCATION = {
    "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "planner",
    "input": {"prompt": "test"},
    "output": {"result": "ok", "confidence": 0.9},
    "context": {"role_declared": True, "schema_exists": True},
}


def test_aigc_with_passing_custom_gate():
    aigc = AIGC(custom_gates=[PassingGate()])
    audit = aigc.enforce(VALID_INVOCATION)
    assert audit["enforcement_result"] == "PASS"
    gates = audit["metadata"]["gates_evaluated"]
    assert "custom:passing_gate" in gates


def test_aigc_with_failing_custom_gate():
    aigc = AIGC(custom_gates=[FailingGate()])
    with pytest.raises(CustomGateViolationError) as exc_info:
        aigc.enforce(VALID_INVOCATION)
    # CustomGateViolationError is a subclass of GovernanceViolationError
    assert isinstance(exc_info.value, GovernanceViolationError)
    assert exc_info.value.audit_artifact is not None
    assert exc_info.value.audit_artifact["failure_gate"] == "custom_gate_violation"


def test_aigc_custom_gate_ordering_proof():
    """Custom gates appear in gates_evaluated at correct positions."""
    aigc = AIGC(custom_gates=[PreAuthGate(), PassingGate(), PostOutputGate()])
    audit = aigc.enforce(VALID_INVOCATION)
    gates = audit["metadata"]["gates_evaluated"]

    # Pre-auth gate runs first
    pre_auth_idx = gates.index("custom:pre_auth_gate")
    guard_idx = gates.index(GATE_GUARDS)
    assert pre_auth_idx < guard_idx

    # Post-auth gate runs after core auth gates
    post_auth_idx = gates.index("custom:passing_gate")
    assert post_auth_idx > guard_idx

    # Post-output gate runs last
    post_output_idx = gates.index("custom:post_output_gate")
    assert post_output_idx == len(gates) - 1


def test_aigc_validates_gates_at_construction():
    class BadGate(EnforcementGate):
        @property
        def name(self):
            return "bad"

        @property
        def insertion_point(self):
            return "not_valid"

        def evaluate(self, inv, pol, ctx):
            return GateResult()

    with pytest.raises(ValueError):
        AIGC(custom_gates=[BadGate()])


# ── Abstract class ───────────────────────────────────────────────


def test_abstract_gate_cannot_instantiate():
    with pytest.raises(TypeError):
        EnforcementGate()


def test_post_auth_gate_cannot_suppress_role_failure(tmp_path):
    """A post-authorization gate failure cannot suppress a role_validation failure
    that was already recorded.  The artifact must show failure_gate=role_validation."""
    # Policy that only allows 'planner' role
    policy_file = tmp_path / "restricted.yaml"
    policy_file.write_text("policy_version: '1.0'\nroles:\n  - planner\n")

    class AlwaysFailPostAuth(EnforcementGate):
        @property
        def name(self):
            return "always_fail_post_auth"

        @property
        def insertion_point(self):
            return INSERTION_POST_AUTHORIZATION

        def evaluate(self, invocation, policy, context):
            return GateResult(
                passed=False,
                failures=[{"code": "custom_block", "message": "post-auth blocked",
                            "field": None}],
            )

    aigc = AIGC(custom_gates=[AlwaysFailPostAuth()])
    with pytest.raises(GovernanceViolationError) as exc_info:
        aigc.enforce({
            "policy_file": str(policy_file),
            "model_provider": "openai",
            "model_identifier": "gpt-4",
            "role": "admin",          # unauthorized role — role_validation should catch this
            "input": {"prompt": "x"},
            "output": {"result": "y"},
            "context": {},
        })

    artifact = exc_info.value.audit_artifact
    # Role failure must be present — post-auth gate runs AFTER role validation
    assert artifact["failure_gate"] == "role_validation"
