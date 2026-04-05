"""Regression tests for AIGC v0.3.2 audit findings.

Each test class maps to one of the five findings from the
RELEASE_0.3.2_IMPLEMENTATION_AUDIT_2026-04-04.md report and
reproduces the exact failure scenario described there.

Finding 1 — Split Phase B drops pre_output / post_output custom gates
Finding 2 — PreCallResult is forgeable (public constructor bypass)
Finding 3 — PreCallResult is shallow-mutable (nested dict tamper)
Finding 4 — split post-call raises raw TypeError on non-serializable output
Finding 5 — packaging metadata version disagrees with runtime __version__
"""
import importlib.metadata

import pytest

import aigc
from aigc._internal.enforcement import (
    AIGC,
    PreCallResult,
    enforce_post_call,
    enforce_post_call_async,
    enforce_pre_call,
    enforce_pre_call_async,
)
from aigc._internal.errors import (
    CustomGateViolationError,
    InvocationValidationError,
)
from aigc._internal.gates import (
    EnforcementGate,
    GateResult,
    INSERTION_POST_OUTPUT,
    INSERTION_PRE_OUTPUT,
)
from aigc._internal.policy_loader import load_policy


# ── Helpers ────────────────────────────────────────────────────────

GOLDEN_POLICY = "tests/golden_replays/golden_policy_v1.yaml"


def _pre_call_inv(**overrides):
    inv = {
        "policy_file": GOLDEN_POLICY,
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {"query": "test"},
        "context": {"role_declared": True, "schema_exists": True},
    }
    inv.update(overrides)
    return inv


def _valid_output():
    return {"result": "test output", "confidence": 0.95}


# ── Gate fixtures ──────────────────────────────────────────────────

class BlockPreOutput(EnforcementGate):
    """Always-fail gate at pre_output insertion point."""

    @property
    def name(self):
        return "block_pre_output"

    @property
    def insertion_point(self):
        return INSERTION_PRE_OUTPUT

    def evaluate(self, invocation, policy, context):
        return GateResult(
            passed=False,
            failures=[{"code": "PRE_OUTPUT_BLOCKED",
                        "message": "pre_output blocked", "field": None}],
        )


class PassPreOutput(EnforcementGate):
    """Always-pass gate at pre_output with metadata."""

    @property
    def name(self):
        return "pass_pre_output"

    @property
    def insertion_point(self):
        return INSERTION_PRE_OUTPUT

    def evaluate(self, invocation, policy, context):
        return GateResult(passed=True, metadata={"pre_output_ran": True})


class BlockPostOutput(EnforcementGate):
    """Always-fail gate at post_output insertion point."""

    @property
    def name(self):
        return "block_post_output"

    @property
    def insertion_point(self):
        return INSERTION_POST_OUTPUT

    def evaluate(self, invocation, policy, context):
        return GateResult(
            passed=False,
            failures=[{"code": "POST_OUTPUT_BLOCKED",
                        "message": "post_output blocked", "field": None}],
        )


class PassPostOutput(EnforcementGate):
    """Always-pass gate at post_output with metadata."""

    @property
    def name(self):
        return "pass_post_output"

    @property
    def insertion_point(self):
        return INSERTION_POST_OUTPUT

    def evaluate(self, invocation, policy, context):
        return GateResult(passed=True, metadata={"post_output_ran": True})


# ── Finding 1: Phase B custom gates in split mode ─────────────────

class TestFinding1SplitPhaseBCustomGates:
    """Split mode must execute pre_output and post_output custom gates."""

    def test_blocking_pre_output_gate_raises_in_split_module_level(self):
        """A failing pre_output gate must raise in split post-call (module-level)."""
        pre = enforce_pre_call(_pre_call_inv(), custom_gates=[BlockPreOutput()])
        with pytest.raises(CustomGateViolationError):
            enforce_post_call(pre, _valid_output())

    def test_blocking_post_output_gate_raises_in_split_module_level(self):
        """A failing post_output gate must raise in split post-call (module-level)."""
        pre = enforce_pre_call(_pre_call_inv(), custom_gates=[BlockPostOutput()])
        with pytest.raises(CustomGateViolationError):
            enforce_post_call(pre, _valid_output())

    def test_passing_pre_output_gate_metadata_in_split_artifact(self):
        """A passing pre_output gate's metadata must appear in the split artifact."""
        pre = enforce_pre_call(_pre_call_inv(), custom_gates=[PassPreOutput()])
        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["enforcement_result"] == "PASS"
        meta = artifact["metadata"]
        # PassPreOutput returns metadata={"pre_output_ran": True}; the
        # parity checker merges gate metadata values directly into the
        # custom_gate_metadata dict (not keyed by gate name).
        assert meta.get("custom_gate_metadata", {}).get("pre_output_ran") is True, (
            "pre_output gate metadata missing from split artifact"
        )

    def test_passing_post_output_gate_metadata_in_split_artifact(self):
        """A passing post_output gate's metadata must appear in the split artifact."""
        pre = enforce_pre_call(_pre_call_inv(), custom_gates=[PassPostOutput()])
        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["enforcement_result"] == "PASS"
        meta = artifact["metadata"]
        assert meta.get("custom_gate_metadata", {}).get("post_output_ran") is True, (
            "post_output gate metadata missing from split artifact"
        )

    def test_blocking_pre_output_gate_raises_in_aigc_instance(self):
        """A failing pre_output gate must raise in AIGC.enforce_post_call."""
        engine = AIGC(custom_gates=[BlockPreOutput()])
        pre = engine.enforce_pre_call(_pre_call_inv())
        with pytest.raises(CustomGateViolationError):
            engine.enforce_post_call(pre, _valid_output())

    def test_blocking_post_output_gate_raises_in_aigc_instance(self):
        """A failing post_output gate must raise in AIGC.enforce_post_call."""
        engine = AIGC(custom_gates=[BlockPostOutput()])
        pre = engine.enforce_pre_call(_pre_call_inv())
        with pytest.raises(CustomGateViolationError):
            engine.enforce_post_call(pre, _valid_output())

    def test_passing_output_gates_run_in_aigc_instance(self):
        """Passing output-side gates contribute metadata in AIGC split artifact."""
        engine = AIGC(custom_gates=[PassPreOutput(), PassPostOutput()])
        pre = engine.enforce_pre_call(_pre_call_inv())
        artifact = engine.enforce_post_call(pre, _valid_output())
        assert artifact["enforcement_result"] == "PASS"
        cgm = artifact["metadata"].get("custom_gate_metadata", {})
        assert cgm.get("pre_output_ran") is True
        assert cgm.get("post_output_ran") is True

    async def test_blocking_pre_output_gate_raises_in_split_async(self):
        """Async split post-call also enforces pre_output gates."""
        pre = await enforce_pre_call_async(
            _pre_call_inv(), custom_gates=[BlockPreOutput()],
        )
        with pytest.raises(CustomGateViolationError):
            await enforce_post_call_async(pre, _valid_output())


# ── Finding 2: PreCallResult forgery prevention ───────────────────

class TestFinding2PreCallResultForgeryPrevention:
    """Directly-constructed PreCallResult tokens must be rejected at post-call."""

    def _make_forged_token(self):
        """Construct a PreCallResult directly, bypassing enforce_pre_call."""
        policy = load_policy(GOLDEN_POLICY)
        return PreCallResult(
            effective_policy=policy,
            resolved_guards=(),
            resolved_conditions={},
            phase_a_metadata={
                "gates_evaluated": [],
                "pre_call_timestamp": 0,
            },
            invocation_snapshot={
                "policy_file": GOLDEN_POLICY,
                "model_provider": "openai",
                "model_identifier": "gpt-4",
                "role": "attacker",
                "input": {},
                "context": {},
            },
            policy_file=GOLDEN_POLICY,
            model_provider="openai",
            model_identifier="gpt-4",
            role="attacker",
        )

    def test_forged_token_rejected_by_module_level_post_call(self):
        """enforce_post_call must reject a directly-constructed PreCallResult."""
        forged = self._make_forged_token()
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(forged, _valid_output())
        assert exc_info.value.audit_artifact is not None
        assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"

    def test_forged_token_rejected_by_aigc_instance_post_call(self):
        """AIGC.enforce_post_call must reject a directly-constructed PreCallResult."""
        engine = AIGC()
        forged = self._make_forged_token()
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_post_call(forged, _valid_output())
        assert exc_info.value.audit_artifact is not None
        assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"

    def test_real_token_from_enforce_pre_call_is_accepted(self):
        """A token from enforce_pre_call() must pass the provenance check."""
        pre = enforce_pre_call(_pre_call_inv())
        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["enforcement_result"] == "PASS"

    def test_forged_token_error_message_is_descriptive(self):
        """The rejection error message must not be the generic type-check message."""
        forged = self._make_forged_token()
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(forged, _valid_output())
        # The message should not confuse this with a wrong-type argument
        assert "not issued by enforce_pre_call" in str(exc_info.value).lower() or \
               "directly-constructed" in str(exc_info.value).lower()


# ── Finding 3: PreCallResult shallow-mutability ───────────────────

class TestFinding3PreCallResultShallowMutability:
    """Mutations to PreCallResult nested structures must not affect Phase B."""

    def test_mutating_effective_policy_output_schema_does_not_weaken_enforcement(self):
        """Removing a required field from effective_policy must not cause PASS."""
        pre = enforce_pre_call(_pre_call_inv())
        # Remove the 'confidence' required field from the stored policy
        pre.effective_policy["output_schema"]["required"] = ["result"]
        # Even after mutation, the output without 'confidence' should still
        # be checked against the original (deep-copied) policy
        # The golden policy requires 'confidence' — output without it should FAIL
        from aigc._internal.errors import SchemaValidationError
        with pytest.raises(SchemaValidationError):
            enforce_post_call(pre, {"result": "ok"})

    def test_mutating_invocation_snapshot_context_does_not_affect_artifact(self):
        """Mutating invocation_snapshot context must not appear in the audit artifact."""
        pre = enforce_pre_call(_pre_call_inv())
        original_context = dict(pre.invocation_snapshot["context"])
        # Tamper with the stored snapshot
        pre.invocation_snapshot["context"]["session_id"] = "tampered"
        artifact = enforce_post_call(pre, _valid_output())
        # The artifact context must reflect the original, not the tampered value
        assert artifact.get("context", {}).get("session_id") != "tampered", (
            "Tampered session_id must not appear in audit artifact"
        )
        # Original fields must still be present
        for k, v in original_context.items():
            assert artifact.get("context", {}).get(k) == v

    def test_mutating_invocation_snapshot_input_does_not_affect_artifact(self):
        """Mutating invocation_snapshot input must not affect the audit artifact."""
        pre = enforce_pre_call(_pre_call_inv())
        # Mutate the public snapshot; Phase B reads from the frozen copy.
        pre.invocation_snapshot["input"]["injected_key"] = "injected_value"
        artifact = enforce_post_call(pre, _valid_output())
        # The input checksum must match the ORIGINAL input (before mutation).
        from aigc._internal.audit import checksum
        original_input_checksum = checksum({"query": "test"})
        assert artifact["input_checksum"] == original_input_checksum, (
            "Tampered input must not affect the input_checksum in the artifact"
        )

    def test_construction_time_snapshot_is_independent_of_original_invocation(self):
        """Mutating the original invocation after Phase A must not affect Phase B."""
        inv = _pre_call_inv()
        pre = enforce_pre_call(inv)
        # Mutate the original invocation dict after Phase A completes
        inv["input"]["injected"] = "post-phase-a mutation"
        inv["context"]["injected"] = "post-phase-a mutation"
        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["enforcement_result"] == "PASS"
        # The input checksum must match the original, un-mutated input
        from aigc._internal.audit import checksum
        assert artifact["input_checksum"] == checksum({"query": "test"})


# ── Finding 4: Non-serializable output FAIL artifact ─────────────

class TestFinding4NonSerializableOutput:
    """Non-serializable output must produce a typed FAIL artifact, not raw TypeError."""

    def test_non_serializable_output_raises_invocation_validation_error(self):
        """object() in output must raise InvocationValidationError, not TypeError."""
        pre = enforce_pre_call(_pre_call_inv())
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, {"result": object(), "confidence": 0.9})
        exc = exc_info.value
        assert exc.audit_artifact is not None, "FAIL artifact must be attached"
        assert exc.audit_artifact["enforcement_result"] == "FAIL"

    def test_non_serializable_output_pre_call_result_remains_unconsumed(self):
        """After a non-serializable output error, the token must remain unconsumed."""
        pre = enforce_pre_call(_pre_call_inv())
        with pytest.raises(InvocationValidationError):
            enforce_post_call(pre, {"result": object(), "confidence": 0.9})
        # The token should NOT have been consumed (validation fails before _consumed flip)
        assert not pre._consumed

    def test_non_serializable_output_aigc_instance(self):
        """AIGC.enforce_post_call also produces FAIL artifact for non-serializable output."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_post_call(pre, {"result": object(), "confidence": 0.9})
        assert exc_info.value.audit_artifact is not None
        assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"

    def test_non_serializable_nested_value_raises(self):
        """A non-serializable nested value in output must also be caught."""
        pre = enforce_pre_call(_pre_call_inv())
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, {"result": "ok", "data": {"nested": set()}})
        assert exc_info.value.audit_artifact is not None

    def test_serializable_output_passes_normally(self):
        """Normal JSON-serializable output must not trigger the new check."""
        pre = enforce_pre_call(_pre_call_inv())
        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["enforcement_result"] == "PASS"


# ── Finding 5: Packaging metadata version ────────────────────────

class TestFinding5PackagingMetadata:
    """Runtime __version__ and pyproject.toml version must agree."""

    def test_runtime_version_is_0_3_2(self):
        """aigc.__version__ must be 0.3.2."""
        assert aigc.__version__ == "0.3.2"

    def test_pyproject_toml_version_matches_runtime(self):
        """pyproject.toml version must equal aigc.__version__.

        Reads pyproject.toml directly (regex) rather than relying on
        an installed .dist-info, which may be stale in editable installs.
        """
        import re
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        toml_text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(
            r'^version\s*=\s*"([^"]+)"', toml_text, re.MULTILINE,
        )
        assert m, "Could not find version = ... in pyproject.toml"
        toml_version = m.group(1)
        assert toml_version == aigc.__version__, (
            f"pyproject.toml has version {toml_version!r} but "
            f"aigc.__version__ is {aigc.__version__!r}"
        )
