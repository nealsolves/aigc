"""Tests proving custom gate failure classification is correct.

Verifies that custom gate failures produce CustomGateViolationError (not
GovernanceViolationError), map to the "custom_gate_violation" failure_gate,
and produce schema-valid audit artifacts at every insertion point.
"""
import json
from pathlib import Path
from typing import Any, Mapping

import pytest
from jsonschema import validate

from aigc._internal.enforcement import AIGC
from aigc._internal.errors import (
    CustomGateViolationError,
    GovernanceViolationError,
)
from aigc._internal.gates import (
    EnforcementGate,
    GateResult,
    INSERTION_PRE_AUTHORIZATION,
    INSERTION_POST_AUTHORIZATION,
    INSERTION_PRE_OUTPUT,
    INSERTION_POST_OUTPUT,
)

AUDIT_SCHEMA = json.loads(
    Path("schemas/audit_artifact.schema.json").read_text()
)

VALID_INVOCATION = {
    "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "planner",
    "input": {"prompt": "test"},
    "output": {"result": "ok", "confidence": 0.9},
    "context": {"role_declared": True, "schema_exists": True},
}


# ── Helper gate implementations ──────────────────────────────────


class _FailingGate(EnforcementGate):
    """Gate that always fails at a configurable insertion point."""

    def __init__(self, gate_name: str, point: str) -> None:
        self._name = gate_name
        self._point = point

    @property
    def name(self) -> str:
        return self._name

    @property
    def insertion_point(self) -> str:
        return self._point

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        return GateResult(
            passed=False,
            failures=[{
                "code": "CUSTOM_FAIL",
                "message": f"Gate {self._name} blocked",
                "field": None,
            }],
        )


class _PassingGate(EnforcementGate):
    """Gate that always passes at a configurable insertion point."""

    def __init__(self, gate_name: str, point: str) -> None:
        self._name = gate_name
        self._point = point

    @property
    def name(self) -> str:
        return self._name

    @property
    def insertion_point(self) -> str:
        return self._point

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        return GateResult(passed=True)


# ── Test: correct exception type ──────────────────────────────────


class TestCustomGateViolationErrorType:
    """Custom gate failure produces CustomGateViolationError."""

    def test_raises_custom_gate_violation_error(self):
        gate = _FailingGate("blocker", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError):
            aigc.enforce(VALID_INVOCATION)

    def test_does_not_raise_plain_governance_violation(self):
        """The exception type is specifically CustomGateViolationError."""
        gate = _FailingGate("blocker", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        assert type(exc_info.value) is CustomGateViolationError


class TestFailureGateClassification:
    """The audit artifact's failure_gate is 'custom_gate_violation'."""

    def test_failure_gate_is_custom_gate_violation(self):
        gate = _FailingGate("classifier", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        artifact = exc_info.value.audit_artifact
        assert artifact["failure_gate"] == "custom_gate_violation"

    def test_failure_gate_is_not_postcondition_validation(self):
        gate = _FailingGate("classifier", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        artifact = exc_info.value.audit_artifact
        assert artifact["failure_gate"] != "postcondition_validation"


class TestBackwardCompatibility:
    """CustomGateViolationError is a subclass of GovernanceViolationError."""

    def test_is_subclass_of_governance_violation(self):
        assert issubclass(
            CustomGateViolationError, GovernanceViolationError,
        )

    def test_instance_check_against_governance_violation(self):
        gate = _FailingGate("compat", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(GovernanceViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        # Caught as GovernanceViolationError, but is actually Custom
        assert isinstance(exc_info.value, CustomGateViolationError)

    def test_exception_has_audit_artifact(self):
        gate = _FailingGate("compat", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        assert exc_info.value.audit_artifact is not None


class TestArtifactSchemaValidity:
    """The FAIL artifact from a custom gate failure is schema-valid."""

    def test_artifact_validates_against_schema(self):
        gate = _FailingGate("schema_check", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        artifact = exc_info.value.audit_artifact
        # jsonschema.validate raises on schema violation
        validate(artifact, AUDIT_SCHEMA)

    def test_artifact_has_required_fields(self):
        gate = _FailingGate("fields_check", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        artifact = exc_info.value.audit_artifact
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["failure_gate"] == "custom_gate_violation"
        assert artifact["failure_reason"] is not None
        assert isinstance(artifact["failures"], list)
        assert len(artifact["failures"]) >= 1


# ── Tests per insertion point ─────────────────────────────────────


class TestPreAuthGateFailureMapping:
    """Pre-authorization gate failure maps to 'custom_gate_violation'."""

    def test_pre_auth_failure_gate(self):
        gate = _FailingGate("pre_auth_block", INSERTION_PRE_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        artifact = exc_info.value.audit_artifact
        assert artifact["failure_gate"] == "custom_gate_violation"

    def test_pre_auth_artifact_is_schema_valid(self):
        gate = _FailingGate("pre_auth_schema", INSERTION_PRE_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        validate(exc_info.value.audit_artifact, AUDIT_SCHEMA)


class TestPostAuthGateFailureMapping:
    """Post-authorization gate failure maps to 'custom_gate_violation'."""

    def test_post_auth_failure_gate(self):
        gate = _FailingGate("post_auth_block", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        artifact = exc_info.value.audit_artifact
        assert artifact["failure_gate"] == "custom_gate_violation"

    def test_post_auth_artifact_is_schema_valid(self):
        gate = _FailingGate("post_auth_schema", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        validate(exc_info.value.audit_artifact, AUDIT_SCHEMA)


class TestPreOutputGateFailureMapping:
    """Pre-output gate failure maps to 'custom_gate_violation'."""

    def test_pre_output_failure_gate(self):
        gate = _FailingGate("pre_out_block", INSERTION_PRE_OUTPUT)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        artifact = exc_info.value.audit_artifact
        assert artifact["failure_gate"] == "custom_gate_violation"

    def test_pre_output_artifact_is_schema_valid(self):
        gate = _FailingGate("pre_out_schema", INSERTION_PRE_OUTPUT)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        validate(exc_info.value.audit_artifact, AUDIT_SCHEMA)


class TestPostOutputGateFailureMapping:
    """Post-output gate failure maps to 'custom_gate_violation'."""

    def test_post_output_failure_gate(self):
        gate = _FailingGate("post_out_block", INSERTION_POST_OUTPUT)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        artifact = exc_info.value.audit_artifact
        assert artifact["failure_gate"] == "custom_gate_violation"

    def test_post_output_artifact_is_schema_valid(self):
        gate = _FailingGate("post_out_schema", INSERTION_POST_OUTPUT)
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(VALID_INVOCATION)

        validate(exc_info.value.audit_artifact, AUDIT_SCHEMA)


class TestCustomGateDoesNotSuppressCoreFailures:
    """Custom gate failure does NOT suppress core gate failures.

    A pre-auth custom gate that fails should report the custom gate
    failure since it runs before core gates. The core gate failure
    (e.g., role violation) never gets a chance to execute.
    """

    def test_pre_auth_gate_failure_preempts_role_violation(self):
        """Pre-auth gate runs first; role validation never executes."""
        gate = _FailingGate("early_block", INSERTION_PRE_AUTHORIZATION)
        # Use a role that would fail role validation
        bad_role_invocation = {**VALID_INVOCATION, "role": "nonexistent_role"}
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(CustomGateViolationError) as exc_info:
            aigc.enforce(bad_role_invocation)

        artifact = exc_info.value.audit_artifact
        # The failure is the custom gate, not the role violation,
        # because the custom gate ran first and halted the pipeline
        assert artifact["failure_gate"] == "custom_gate_violation"

    def test_passing_pre_auth_gate_allows_core_failure_through(self):
        """A passing custom gate does not mask a subsequent core failure."""
        gate = _PassingGate("permissive", INSERTION_PRE_AUTHORIZATION)
        bad_role_invocation = {**VALID_INVOCATION, "role": "nonexistent_role"}
        aigc = AIGC(custom_gates=[gate])

        with pytest.raises(GovernanceViolationError) as exc_info:
            aigc.enforce(bad_role_invocation)

        artifact = exc_info.value.audit_artifact
        # The role validation failure comes through because the custom
        # gate passed
        assert artifact["failure_gate"] == "role_validation"
        # The custom gate was still evaluated
        assert "custom:permissive" in artifact["metadata"]["gates_evaluated"]
