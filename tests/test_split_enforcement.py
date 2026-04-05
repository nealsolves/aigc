"""
Split enforcement tests.

Validates the two-phase enforce_pre_call() / enforce_post_call() API
alongside the existing unified enforce_invocation() path.
"""

import pytest

from aigc._internal.enforcement import (
    PreCallResult,
    enforce_invocation,
    enforce_post_call,
    enforce_pre_call,
    enforce_pre_call_async,
    enforce_post_call_async,
)
from aigc._internal.errors import (
    GovernanceViolationError,
    InvocationValidationError,
    SchemaValidationError,
)


# ── Helpers ──────────────────────────────────────────────────────

def _pre_call_invocation(**overrides):
    """Minimal valid pre-call invocation (no output)."""
    inv = {
        "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {"query": "test"},
        "context": {"role_declared": True, "schema_exists": True},
    }
    inv.update(overrides)
    return inv


def _valid_output():
    """Output that satisfies the golden policy schema."""
    return {"result": "test output", "confidence": 0.95}


def _unified_invocation(**overrides):
    """Minimal valid unified invocation (with output)."""
    inv = _pre_call_invocation(**overrides)
    inv["output"] = _valid_output()
    return inv


# ── Basic split path ────────────────────────────────────────────

class TestBasicSplitPath:

    def test_enforce_pre_call_returns_pre_call_result(self):
        """Basic happy path: enforce_pre_call returns a PreCallResult."""
        result = enforce_pre_call(_pre_call_invocation())
        assert isinstance(result, PreCallResult)
        assert result.policy_file == (
            "tests/golden_replays/golden_policy_v1.yaml"
        )
        assert result.model_provider == "openai"
        assert result.model_identifier == "gpt-4"
        assert result.role == "planner"

    def test_enforce_post_call_returns_audit_artifact(self):
        """Happy path end-to-end: pre_call + post_call produces artifact."""
        pre = enforce_pre_call(_pre_call_invocation())
        audit = enforce_post_call(pre, _valid_output())

        assert audit["enforcement_result"] == "PASS"
        assert audit["model_provider"] == "openai"
        assert audit["model_identifier"] == "gpt-4"
        assert audit["role"] == "planner"

    def test_split_artifact_enforcement_mode_is_split(self):
        """Artifact from split path has enforcement_mode='split'."""
        pre = enforce_pre_call(_pre_call_invocation())
        audit = enforce_post_call(pre, _valid_output())

        assert audit["metadata"]["enforcement_mode"] == "split"

    def test_split_artifact_has_phase_gate_lists(self):
        """Split artifact has pre/post_call_gates_evaluated."""
        pre = enforce_pre_call(_pre_call_invocation())
        audit = enforce_post_call(pre, _valid_output())

        meta = audit["metadata"]
        assert "pre_call_gates_evaluated" in meta
        assert "post_call_gates_evaluated" in meta
        assert isinstance(meta["pre_call_gates_evaluated"], list)
        assert isinstance(meta["post_call_gates_evaluated"], list)

        # Phase A gates
        assert "guard_evaluation" in meta["pre_call_gates_evaluated"]
        assert "role_validation" in meta["pre_call_gates_evaluated"]
        assert "precondition_validation" in meta["pre_call_gates_evaluated"]
        assert "tool_constraint_validation" in (
            meta["pre_call_gates_evaluated"]
        )

        # Phase B gates
        assert "schema_validation" in meta["post_call_gates_evaluated"]
        assert "postcondition_validation" in (
            meta["post_call_gates_evaluated"]
        )

    def test_split_artifact_has_timestamps(self):
        """Split artifact has pre/post_call_timestamp."""
        pre = enforce_pre_call(_pre_call_invocation())
        audit = enforce_post_call(pre, _valid_output())

        meta = audit["metadata"]
        assert "pre_call_timestamp" in meta
        assert "post_call_timestamp" in meta
        assert isinstance(meta["pre_call_timestamp"], int)
        assert isinstance(meta["post_call_timestamp"], int)
        assert meta["post_call_timestamp"] >= meta["pre_call_timestamp"]


# ── Phase A FAIL ────────────────────────────────────────────────

class TestPhaseAFail:

    def test_phase_a_fail_role_raises(self):
        """Role not in policy raises GovernanceViolationError."""
        inv = _pre_call_invocation(role="attacker")

        with pytest.raises(GovernanceViolationError) as exc_info:
            enforce_pre_call(inv)

        assert exc_info.value.audit_artifact is not None
        assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"

    def test_phase_a_fail_artifact_mode_is_split_pre_call_only(self):
        """Phase A FAIL artifact has enforcement_mode='split_pre_call_only'."""
        inv = _pre_call_invocation(role="attacker")

        with pytest.raises(GovernanceViolationError) as exc_info:
            enforce_pre_call(inv)

        artifact = exc_info.value.audit_artifact
        assert artifact["metadata"]["enforcement_mode"] == (
            "split_pre_call_only"
        )

    def test_phase_a_fail_does_not_require_output(self):
        """No output field needed in the invocation for pre-call."""
        inv = _pre_call_invocation(role="attacker")
        assert "output" not in inv

        with pytest.raises(GovernanceViolationError):
            enforce_pre_call(inv)

    def test_phase_a_fail_has_partial_gates(self):
        """Phase A FAIL artifact records gates evaluated before failure."""
        inv = _pre_call_invocation(role="attacker")

        with pytest.raises(GovernanceViolationError) as exc_info:
            enforce_pre_call(inv)

        artifact = exc_info.value.audit_artifact
        gates = artifact["metadata"]["pre_call_gates_evaluated"]
        # Guards ran successfully before role validation failed
        assert "guard_evaluation" in gates
        # Role validation failed, so it should NOT be in the list
        assert "role_validation" not in gates


# ── Phase B FAIL ────────────────────────────────────────────────

class TestPhaseBFail:

    def test_phase_b_fail_schema_raises(self):
        """Schema validation failure after Phase A pass raises."""
        pre = enforce_pre_call(_pre_call_invocation())

        # Output missing required 'confidence' field
        bad_output = {"result": "test"}

        with pytest.raises(SchemaValidationError) as exc_info:
            enforce_post_call(pre, bad_output)

        artifact = exc_info.value.audit_artifact
        assert artifact["enforcement_result"] == "FAIL"

    def test_phase_b_fail_artifact_mode_is_split(self):
        """Phase B FAIL artifact has enforcement_mode='split'."""
        pre = enforce_pre_call(_pre_call_invocation())

        with pytest.raises(SchemaValidationError) as exc_info:
            enforce_post_call(pre, {"result": "test"})

        artifact = exc_info.value.audit_artifact
        assert artifact["metadata"]["enforcement_mode"] == "split"


# ── Validation ──────────────────────────────────────────────────

class TestValidation:

    def test_enforce_pre_call_missing_required_field_raises(self):
        """Missing required field raises InvocationValidationError."""
        inv = _pre_call_invocation()
        del inv["role"]

        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_pre_call(inv)

        assert "missing_fields" in exc_info.value.details
        assert "role" in exc_info.value.details["missing_fields"]

    def test_enforce_post_call_wrong_type_raises(self):
        """Non-PreCallResult arg raises InvocationValidationError."""
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call("not a PreCallResult", {})

        assert "received_type" in exc_info.value.details

    def test_enforce_post_call_reuse_raises(self):
        """Second call on same PreCallResult raises."""
        pre = enforce_pre_call(_pre_call_invocation())
        enforce_post_call(pre, _valid_output())

        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, _valid_output())

        assert "already been consumed" in str(exc_info.value)

    def test_enforce_post_call_invalid_output_type_raises(self):
        """Non-dict output raises InvocationValidationError."""
        pre = enforce_pre_call(_pre_call_invocation())

        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, "not a dict")

        assert "output must be a dict" in str(exc_info.value)


# ── Unified backward compat ─────────────────────────────────────

class TestUnifiedBackwardCompat:

    def test_enforce_invocation_still_works(self):
        """Existing API still returns a valid artifact."""
        inv = _unified_invocation()
        audit = enforce_invocation(inv)

        assert audit["enforcement_result"] == "PASS"
        assert audit["model_provider"] == "openai"
        assert audit["role"] == "planner"

    def test_unified_artifact_enforcement_mode_is_unified(self):
        """Unified artifact does NOT have enforcement_mode in metadata.

        The unified path preserves exact backward compatibility: metadata
        contains gates_evaluated (combined list), no enforcement_mode key.
        """
        inv = _unified_invocation()
        audit = enforce_invocation(inv)

        # Unified mode preserves backward compat: no enforcement_mode key
        assert "enforcement_mode" not in audit["metadata"]
        # But gates_evaluated is still present as before
        assert "gates_evaluated" in audit["metadata"]


# ── Async parity ────────────────────────────────────────────────

class TestAsyncParity:

    @pytest.mark.asyncio
    async def test_enforce_pre_call_async_returns_pre_call_result(self):
        """Async pre_call returns PreCallResult."""
        result = await enforce_pre_call_async(_pre_call_invocation())
        assert isinstance(result, PreCallResult)

    @pytest.mark.asyncio
    async def test_enforce_post_call_async_returns_audit_artifact(self):
        """Async post_call returns a valid audit artifact."""
        pre = await enforce_pre_call_async(_pre_call_invocation())
        audit = await enforce_post_call_async(pre, _valid_output())

        assert audit["enforcement_result"] == "PASS"
        assert audit["metadata"]["enforcement_mode"] == "split"
