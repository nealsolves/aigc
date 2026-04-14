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


# ── Gates returning malformed (non-dict) failure entries ─────────

class StringFailureGate(EnforcementGate):
    """Gate that returns a plain string as a failure entry.

    Uses pre_output (Phase B) to exercise the sanitization loop
    where the P1 crash occurs.
    """

    @property
    def name(self):
        return "string_failure_gate"

    @property
    def insertion_point(self):
        return "pre_output"

    def evaluate(self, invocation, policy, context):
        from aigc._internal.gates import GateResult
        return GateResult(passed=False, failures=["raw string failure"])


class MixedFailureGate(EnforcementGate):
    """Gate that mixes valid dict failures with non-dict entries.

    Uses pre_output (Phase B) to exercise the sanitization loop
    where the P1 crash occurs.
    """

    @property
    def name(self):
        return "mixed_failure_gate"

    @property
    def insertion_point(self):
        return "pre_output"

    def evaluate(self, invocation, policy, context):
        from aigc._internal.gates import GateResult
        return GateResult(
            passed=False,
            failures=[
                {"code": "REAL_FAILURE", "message": "valid entry", "field": None},
                42,
                {"code": "ANOTHER_REAL", "message": "also valid", "field": None},
            ],
        )


class PhaseAStringFailureGate(EnforcementGate):
    """Gate that returns a plain string failure at pre_authorization (Phase A).

    Pins Site 1 fix: failures[0].get() in _make_custom_gate_runner must not
    crash when the first failure entry is not a dict.
    """

    @property
    def name(self):
        return "phase_a_string_failure_gate"

    @property
    def insertion_point(self):
        return "pre_authorization"

    def evaluate(self, invocation, policy, context):
        from aigc._internal.gates import GateResult
        return GateResult(passed=False, failures=["pre-auth string failure"])


class TestMalformedGateFailuresNormalized:
    """P1 regression: non-dict gate failure entries must not crash the error path.

    Before the fix, gf.get() / {**gf, ...} would raise AttributeError/TypeError
    on non-dict entries, replacing the governance exception with an internal crash
    and preventing the FAIL artifact from being attached.
    """

    def test_string_failure_raises_governance_error_not_crash(self, base_invocation):
        aigc = AIGC(custom_gates=[StringFailureGate()])
        with pytest.raises(CustomGateViolationError):
            aigc.enforce(base_invocation)

    def test_string_failure_attaches_fail_artifact(self, base_invocation):
        aigc = AIGC(custom_gates=[StringFailureGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"

    def test_string_failure_normalized_to_malformed_code(self, base_invocation):
        # Sanitized failures land in the audit artifact, not exc.details.
        aigc = AIGC(custom_gates=[StringFailureGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        failures = artifact.get("failures") or []
        codes = [f["code"] for f in failures if isinstance(f, dict)]
        assert "CUSTOM_GATE_MALFORMED_FAILURE" in codes

    def test_string_failure_message_preserved(self, base_invocation):
        aigc = AIGC(custom_gates=[StringFailureGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        failures = artifact.get("failures") or []
        malformed = [f for f in failures if isinstance(f, dict)
                     and f.get("code") == "CUSTOM_GATE_MALFORMED_FAILURE"]
        assert len(malformed) == 1
        assert "raw string failure" in malformed[0]["message"]

    def test_mixed_failures_dict_entries_preserved(self, base_invocation):
        aigc = AIGC(custom_gates=[MixedFailureGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        failures = artifact.get("failures") or []
        codes = [f["code"] for f in failures if isinstance(f, dict)]
        assert "REAL_FAILURE" in codes
        assert "ANOTHER_REAL" in codes
        assert "CUSTOM_GATE_MALFORMED_FAILURE" in codes

    def test_mixed_failures_artifact_emitted_to_sink(self, base_invocation):
        emitted = []
        from aigc._internal.sinks import CallbackAuditSink
        sink = CallbackAuditSink(lambda a: emitted.append(a))
        aigc = AIGC(custom_gates=[MixedFailureGate()], sink=sink)
        with pytest.raises(CustomGateViolationError):
            aigc.enforce(base_invocation)

        assert len(emitted) == 1
        assert emitted[0]["enforcement_result"] == "FAIL"

    def test_phase_a_string_failure_does_not_crash(self, base_invocation):
        # Site 1 regression: failures[0].get() in _make_custom_gate_runner
        # must not raise AttributeError when the first failure is not a dict.
        # Phase A handler synthesizes a single wrapper failure, so the artifact
        # shows CustomGateViolationError — the key assertion is no internal crash.
        aigc = AIGC(custom_gates=[PhaseAStringFailureGate()])
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"
        # The Phase A exception message must surface the raw string value, not
        # crash — confirm the string was coerced and forwarded.
        assert "pre-auth string failure" in str(exc_info.value)

    def test_malformed_failure_message_is_sanitized(self, base_invocation):
        # P1 regression: str(gf) must pass through sanitize_failure_message
        # before being stored in the artifact.  A non-dict entry containing
        # a secret must be redacted, not emitted verbatim.
        import re
        secret_pattern = [("test_secret", re.compile(r"TOPSECRET-\w+"))]

        class SecretStringFailureGate(EnforcementGate):
            @property
            def name(self):
                return "secret_string_failure_gate"

            @property
            def insertion_point(self):
                return "pre_output"

            def evaluate(self, invocation, policy, context):
                from aigc._internal.gates import GateResult
                return GateResult(
                    passed=False,
                    failures=["gate failed: TOPSECRET-abc123xyz"],
                )

        aigc_instance = AIGC(
            custom_gates=[SecretStringFailureGate()],
            redaction_patterns=secret_pattern,
        )
        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc_instance.enforce(base_invocation)

        artifact = exc_info.value.audit_artifact
        failures = artifact.get("failures") or []
        malformed = [f for f in failures if isinstance(f, dict)
                     and f.get("code") == "CUSTOM_GATE_MALFORMED_FAILURE"]
        assert len(malformed) == 1
        # Secret must be redacted
        assert "TOPSECRET-abc123xyz" not in malformed[0]["message"]
        assert "[REDACTED:test_secret]" in malformed[0]["message"]
        # Redacted field must be tracked in the artifact metadata
        redacted = artifact.get("metadata", {}).get("redacted_fields", [])
        assert "test_secret" in redacted
