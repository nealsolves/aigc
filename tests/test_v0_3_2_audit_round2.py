"""Regression tests for AIGC v0.3.2 Round 2 audit findings.

Each test class maps to one finding from
RELEASE_0.3.2_IMPLEMENTATION_AUDIT_2026-04-04_v2.md.

Finding 1 — Phase B trusts mutable _frozen_effective_policy
Finding 2 — Audit artifact evidence forged via mutable PreCallResult fields
Finding 3 — Async enforce_pre_call_async captures wrong Phase B gate set
Finding 4 — Unified pre-pipeline FAIL artifacts omit metadata.enforcement_mode
"""
import pytest

from aigc._internal.enforcement import (
    AIGC,
    enforce_invocation,
    enforce_post_call,
    enforce_post_call_async,
    enforce_pre_call,
    enforce_pre_call_async,
)
from aigc._internal.errors import (
    InvocationValidationError,
    SchemaValidationError,
)
from aigc._internal.gates import (
    EnforcementGate,
    GateResult,
    INSERTION_POST_OUTPUT,
    INSERTION_PRE_AUTHORIZATION,
    INSERTION_PRE_OUTPUT,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _unified_inv(**overrides):
    inv = _pre_call_inv(**overrides)
    inv["output"] = {"result": "ok", "confidence": 0.9}
    return inv


def _valid_output():
    return {"result": "test output", "confidence": 0.95}


# ── Finding 1: Phase B trusts mutable _frozen_effective_policy ───────────────

class TestFinding1FrozenPolicyMutability:
    """
    _frozen_effective_policy is a dict; Phase B reads shallow copies of it.
    Mutations to nested dicts (e.g. output_schema.required) propagate into
    Phase B enforcement and can bypass schema validation.
    """

    def test_frozen_policy_mutation_does_not_bypass_schema_module_level(self):
        """
        Mutating _frozen_effective_policy["output_schema"]["required"] after
        Phase A must not allow Phase B to pass with a non-conforming output.
        """
        pre = enforce_pre_call(_pre_call_inv())
        # Weaken schema: remove "confidence" from required
        pre._frozen_effective_policy["output_schema"]["required"] = ["result"]
        # Output is missing "confidence" — should still fail schema validation
        with pytest.raises(SchemaValidationError):
            enforce_post_call(pre, {"result": "ok"})

    def test_frozen_policy_mutation_does_not_bypass_schema_aigc_instance(self):
        """Same test via AIGC instance enforce_post_call."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        pre._frozen_effective_policy["output_schema"]["required"] = ["result"]
        with pytest.raises(SchemaValidationError):
            engine.enforce_post_call(pre, {"result": "ok"})

    def test_effective_policy_field_mutation_does_not_bypass_schema(self):
        """
        Mutating the public effective_policy field (not the frozen copy) must
        also not weaken Phase B enforcement — _frozen_effective_policy should
        be the authoritative source.
        """
        pre = enforce_pre_call(_pre_call_inv())
        pre.effective_policy["output_schema"]["required"] = ["result"]
        with pytest.raises(SchemaValidationError):
            enforce_post_call(pre, {"result": "ok"})


# ── Finding 2: Mutable PreCallResult fields forge audit evidence ──────────────

class TestFinding2MutableFieldArtifactForgery:
    """
    phase_a_metadata and invocation_snapshot are public, mutable dicts.
    Post-call reads from them to build audit artifacts, allowing evidence
    tampering without re-running Phase A.
    """

    def test_phase_a_metadata_mutation_does_not_alter_pass_artifact(self):
        """
        Mutating phase_a_metadata["gates_evaluated"] after Phase A must not
        appear in the Phase B PASS artifact's pre_call_gates_evaluated.
        """
        pre = enforce_pre_call(_pre_call_inv())
        original_gates = list(pre.phase_a_metadata.get("gates_evaluated", []))
        # Inject a forged gate name into the mutable metadata
        pre.phase_a_metadata["gates_evaluated"] = ["forged_gate"]
        pre.phase_a_metadata["pre_call_timestamp"] = 1

        artifact = enforce_post_call(pre, _valid_output())

        # The artifact must reflect actual Phase A gates, not the forged value
        actual_pre_gates = artifact["metadata"].get(
            "pre_call_gates_evaluated", []
        )
        assert actual_pre_gates == original_gates, (
            f"Artifact reflected forged gate list: {actual_pre_gates!r}; "
            f"expected original: {original_gates!r}"
        )

    def test_invocation_snapshot_mutation_does_not_forge_fail_artifact_identity(self):
        """
        Mutating invocation_snapshot["policy_file"] before triggering a
        post-call FAIL must not appear in the FAIL artifact's policy_file.
        """
        pre = enforce_pre_call(_pre_call_inv())
        real_policy = pre.invocation_snapshot["policy_file"]

        # Tamper with the public field
        pre.invocation_snapshot["policy_file"] = "tampered.yaml"

        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, "not a dict")  # triggers output type FAIL

        artifact = exc_info.value.audit_artifact
        assert artifact["policy_file"] == real_policy, (
            f"FAIL artifact used tampered policy_file "
            f"{artifact['policy_file']!r} instead of {real_policy!r}"
        )

    def test_invocation_snapshot_mutation_does_not_forge_aigc_fail_artifact(self):
        """Same invocation_snapshot tamper test via AIGC instance."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        real_policy = pre.invocation_snapshot["policy_file"]
        pre.invocation_snapshot["policy_file"] = "tampered.yaml"

        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_post_call(pre, "not a dict")

        artifact = exc_info.value.audit_artifact
        assert artifact["policy_file"] == real_policy

    def test_phase_a_metadata_mutation_does_not_alter_aigc_pass_artifact(self):
        """phase_a_metadata tamper via AIGC instance."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        original_gates = list(pre.phase_a_metadata.get("gates_evaluated", []))
        pre.phase_a_metadata["gates_evaluated"] = ["forged_gate"]

        artifact = engine.enforce_post_call(pre, _valid_output())

        actual_pre_gates = artifact["metadata"].get(
            "pre_call_gates_evaluated", []
        )
        assert actual_pre_gates == original_gates


# ── Finding 3: Async enforce_pre_call_async captures wrong gate set ───────────

class _MutatingPreAuthGate(EnforcementGate):
    """
    A pre_authorization gate (runs during Phase A) that removes a sibling
    pre_output gate from engine._custom_gates while Phase A executes.

    In the async path, the token is stamped with sort_gates(self._custom_gates)
    AFTER Phase A completes, so the blocker has already been removed from the
    live list and disappears from _phase_b_grouped_gates.

    In the sync path, grouped_gates was captured BEFORE Phase A started, so
    the blocker survives in _phase_b_grouped_gates regardless of mutation.
    """

    def __init__(self, engine, sibling_to_remove):
        self._engine = engine
        self._sibling = sibling_to_remove

    @property
    def name(self):
        return "mutating_pre_auth_gate"

    @property
    def insertion_point(self):
        return INSERTION_PRE_AUTHORIZATION

    def evaluate(self, invocation, policy, context):
        # Mutate the engine's live gate list during Phase A execution
        try:
            self._engine._custom_gates.remove(self._sibling)
        except (ValueError, AttributeError):
            pass
        return GateResult(passed=True)


class _BlockingPreOutputGate(EnforcementGate):
    """Always-fail gate at pre_output — must survive Phase A gate-list mutation."""

    @property
    def name(self):
        return "blocking_pre_output"

    @property
    def insertion_point(self):
        return INSERTION_PRE_OUTPUT

    def evaluate(self, invocation, policy, context):
        return GateResult(
            passed=False,
            failures=[{"code": "BLOCKED", "message": "blocked", "field": None}],
        )


class TestFinding3AsyncGateCaptureParity:
    """
    enforce_pre_call_async() must capture grouped_gates at the start of
    Phase A and stamp that captured set into the token — not re-read
    self._custom_gates at token-stamp time (after Phase A may have mutated it).
    """

    def test_sync_instance_enforce_pre_call_blocks_on_mutated_gates(self):
        """
        Baseline: sync enforce_pre_call uses gates captured before Phase A,
        so the blocker survives the mutating gate removing it from _custom_gates.
        """
        from aigc._internal.errors import CustomGateViolationError

        blocker = _BlockingPreOutputGate()
        engine = AIGC(custom_gates=[])
        mutator = _MutatingPreAuthGate(engine, blocker)
        # Bypass constructor validation by setting directly
        engine._custom_gates = [mutator, blocker]

        pre = engine.enforce_pre_call(_pre_call_inv())
        with pytest.raises(CustomGateViolationError):
            engine.enforce_post_call(pre, _valid_output())

    async def test_async_instance_enforce_pre_call_async_blocks_on_mutated_gates(self):
        """
        enforce_pre_call_async() must also use the gates captured at the
        start of Phase A, not re-read self._custom_gates at stamp time.
        Without the fix, the blocker is removed during Phase A and absent
        from _phase_b_grouped_gates, causing an UNEXPECTED_PASS.
        """
        from aigc._internal.errors import CustomGateViolationError

        blocker = _BlockingPreOutputGate()
        engine = AIGC(custom_gates=[])
        mutator = _MutatingPreAuthGate(engine, blocker)
        engine._custom_gates = [mutator, blocker]

        pre = await engine.enforce_pre_call_async(_pre_call_inv())
        with pytest.raises(CustomGateViolationError):
            engine.enforce_post_call(pre, _valid_output())


# ── Finding 4: Unified pre-pipeline FAIL artifacts missing enforcement_mode ───

class TestFinding4UnifiedPrePipelineEnforcementMode:
    """
    Pre-pipeline failures in unified mode (enforce_invocation and AIGC.enforce)
    must carry metadata.enforcement_mode = "unified" per spec Section 11.2.
    """

    def test_module_level_enforce_invocation_missing_output_fail_has_mode(self):
        """
        enforce_invocation() with missing 'output' field raises
        InvocationValidationError whose artifact has enforcement_mode=unified.
        """
        inv = _pre_call_inv()  # no output key
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_invocation(inv)
        artifact = exc_info.value.audit_artifact
        assert artifact["metadata"].get("enforcement_mode") == "unified", (
            f"Expected enforcement_mode=unified, got "
            f"{artifact['metadata'].get('enforcement_mode')!r}"
        )

    def test_module_level_enforce_invocation_bad_policy_fail_has_mode(self):
        """
        enforce_invocation() with a nonexistent policy file raises and the
        artifact must carry enforcement_mode=unified.
        """
        inv = _unified_inv(policy_file="nonexistent_policy.yaml")
        with pytest.raises(Exception) as exc_info:
            enforce_invocation(inv)
        exc = exc_info.value
        artifact = getattr(exc, "audit_artifact", None)
        assert artifact is not None, "Expected audit_artifact on exception"
        assert artifact["metadata"].get("enforcement_mode") == "unified"

    def test_aigc_instance_enforce_missing_output_fail_has_mode(self):
        """
        AIGC.enforce() with missing 'output' raises and the artifact must
        carry enforcement_mode=unified.
        """
        engine = AIGC()
        inv = _pre_call_inv()  # no output
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce(inv)
        artifact = exc_info.value.audit_artifact
        assert artifact["metadata"].get("enforcement_mode") == "unified"

    def test_aigc_instance_enforce_bad_policy_fail_has_mode(self):
        """AIGC.enforce() with bad policy: artifact must carry enforcement_mode=unified."""
        engine = AIGC()
        inv = _unified_inv(policy_file="nonexistent_policy.yaml")
        with pytest.raises(Exception) as exc_info:
            engine.enforce(inv)
        exc = exc_info.value
        artifact = getattr(exc, "audit_artifact", None)
        assert artifact is not None
        assert artifact["metadata"].get("enforcement_mode") == "unified"

    async def test_module_level_enforce_invocation_async_missing_output_fail_has_mode(self):
        """enforce_invocation_async() with missing output: artifact has mode=unified."""
        from aigc._internal.enforcement import enforce_invocation_async

        inv = _pre_call_inv()
        with pytest.raises(InvocationValidationError) as exc_info:
            await enforce_invocation_async(inv)
        artifact = exc_info.value.audit_artifact
        assert artifact["metadata"].get("enforcement_mode") == "unified"

    async def test_aigc_instance_enforce_async_missing_output_fail_has_mode(self):
        """AIGC.enforce_async() with missing output: artifact has mode=unified."""
        engine = AIGC()
        inv = _pre_call_inv()
        with pytest.raises(InvocationValidationError) as exc_info:
            await engine.enforce_async(inv)
        artifact = exc_info.value.audit_artifact
        assert artifact["metadata"].get("enforcement_mode") == "unified"
