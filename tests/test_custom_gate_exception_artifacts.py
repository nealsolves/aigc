"""
Regression tests for custom gate exception → FAIL artifact guarantee.

Proves that:
- A custom gate raising a non-read-only TypeError produces a FAIL artifact
  and raises a typed AIGCError (CustomGateViolationError).
- A custom gate raising a read-only TypeError (mutation attempt) still
  produces the existing CUSTOM_GATE_MUTATION failure code.
- The failure_gate in the artifact is deterministic.

These tests close audit finding C1.
"""

import os
import tempfile

import pytest

from aigc._internal.enforcement import AIGC
from aigc._internal.errors import CustomGateViolationError
from aigc._internal.gates import EnforcementGate, GateResult


# ── Fixtures ────────────────────────────────────────────────────

POLICY_YAML = """\
policy_version: "1.0"
roles:
  - analyst
pre_conditions:
  required:
    has_session:
      type: boolean
"""


@pytest.fixture()
def policy_path(tmp_path):
    p = tmp_path / "policy.yaml"
    p.write_text(POLICY_YAML)
    return str(p)


@pytest.fixture()
def base_invocation(policy_path):
    return {
        "policy_file": policy_path,
        "model_provider": "test",
        "model_identifier": "test-model",
        "role": "analyst",
        "input": {"prompt": "hello"},
        "output": {"text": "world"},
        "context": {"has_session": True},
    }


# ── Gate that raises a non-read-only TypeError ──────────────────

class NonReadOnlyTypeErrorGate(EnforcementGate):
    """Gate that raises a TypeError unrelated to immutability."""

    @property
    def name(self):
        return "non_readonly_typeerror_gate"

    @property
    def insertion_point(self):
        return "pre_authorization"

    def evaluate(self, invocation, policy, context):
        # Simulate a bug in gate code: wrong argument types
        raise TypeError("unsupported operand type(s) for +: 'int' and 'str'")


class ReadOnlyTypeErrorGate(EnforcementGate):
    """Gate that triggers the read-only mutation protection."""

    @property
    def name(self):
        return "mutation_gate"

    @property
    def insertion_point(self):
        return "pre_authorization"

    def evaluate(self, invocation, policy, context):
        # Attempt to mutate read-only invocation view
        invocation["role"] = "admin"
        return GateResult(passed=True)


class GenericExceptionGate(EnforcementGate):
    """Gate that raises a generic exception."""

    @property
    def name(self):
        return "generic_exception_gate"

    @property
    def insertion_point(self):
        return "pre_authorization"

    def evaluate(self, invocation, policy, context):
        raise RuntimeError("unexpected gate failure")


# ── Tests ────────────────────────────────────────────────────────

class TestNonReadOnlyTypeErrorProducesFAILArtifact:
    """C1 regression: non-read-only TypeError must produce FAIL artifact."""

    def test_raises_custom_gate_violation_error(self, base_invocation):
        aigc = AIGC(custom_gates=[NonReadOnlyTypeErrorGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        exc = exc_info.value
        assert isinstance(exc, CustomGateViolationError)

    def test_fail_artifact_attached(self, base_invocation):
        aigc = AIGC(custom_gates=[NonReadOnlyTypeErrorGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"

    def test_failure_gate_is_deterministic(self, base_invocation):
        aigc = AIGC(custom_gates=[NonReadOnlyTypeErrorGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact["failure_gate"] == "custom_gate_violation"

    def test_artifact_emitted_to_sink(self, base_invocation):
        emitted = []
        from aigc._internal.sinks import CallbackAuditSink
        sink = CallbackAuditSink(lambda a: emitted.append(a))
        aigc = AIGC(
            custom_gates=[NonReadOnlyTypeErrorGate()],
            sink=sink,
        )
        with pytest.raises(CustomGateViolationError):
            aigc.enforce(base_invocation)

        assert len(emitted) == 1
        assert emitted[0]["enforcement_result"] == "FAIL"


class TestReadOnlyTypeErrorStillWorks:
    """Existing read-only mutation protection must not regress."""

    def test_mutation_produces_fail_artifact(self, base_invocation):
        aigc = AIGC(custom_gates=[ReadOnlyTypeErrorGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"

    def test_mutation_failure_code(self, base_invocation):
        aigc = AIGC(custom_gates=[ReadOnlyTypeErrorGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact["failure_gate"] == "custom_gate_violation"


class TestGenericExceptionStillWrapped:
    """Generic exceptions from gates must also produce FAIL artifacts."""

    def test_generic_exception_produces_artifact(self, base_invocation):
        aigc = AIGC(custom_gates=[GenericExceptionGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["failure_gate"] == "custom_gate_violation"
