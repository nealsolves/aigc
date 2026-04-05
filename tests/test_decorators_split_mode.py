"""
@governed decorator split-enforcement mode tests.

Validates pre_call_enforcement=True behavior:
- Phase A blocks function execution on failure
- Phase A pass allows function execution
- Phase B failure after function execution
- Async parity
- Default mode regression
"""

from __future__ import annotations

import pytest

from aigc._internal.decorators import governed
from aigc._internal.errors import (
    GovernanceViolationError,
    SchemaValidationError,
)

POLICY = "tests/golden_replays/golden_policy_v1.yaml"
PROVIDER = "anthropic"
MODEL = "claude-sonnet-4-5-20250929"
ROLE = "planner"

VALID_INPUT = {"task": "analyse system"}
VALID_CONTEXT = {"role_declared": True, "schema_exists": True}
VALID_OUTPUT = {"result": "analysis complete", "confidence": 0.95}
BAD_SCHEMA_OUTPUT = {"result": "test"}  # missing required 'confidence'


# ── Sync split-enforcement tests ──────────────────────────────


class TestGovernedSplitSync:

    def test_governed_split_blocks_function_on_phase_a_fail(self):
        """Phase A role failure prevents the wrapped function from running."""
        side_effects: list[str] = []

        @governed(
            policy_file=POLICY,
            role="unauthorized_role",
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=True,
        )
        def guarded_fn(input_data, context):
            side_effects.append("called")
            return VALID_OUTPUT

        with pytest.raises(GovernanceViolationError):
            guarded_fn(VALID_INPUT, VALID_CONTEXT)

        assert side_effects == [], (
            "Function body must NOT execute when Phase A fails"
        )

    def test_governed_split_executes_function_on_phase_a_pass(self):
        """Phase A passes, function runs, Phase B passes; return value OK."""
        @governed(
            policy_file=POLICY,
            role=ROLE,
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=True,
        )
        def guarded_fn(input_data, context):
            return VALID_OUTPUT

        result = guarded_fn(VALID_INPUT, VALID_CONTEXT)
        assert result == VALID_OUTPUT

    def test_governed_split_phase_b_fail_after_function_runs(self):
        """Phase A passes, function runs, Phase B fails on schema."""
        side_effects: list[str] = []

        @governed(
            policy_file=POLICY,
            role=ROLE,
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=True,
        )
        def guarded_fn(input_data, context):
            side_effects.append("called")
            return BAD_SCHEMA_OUTPUT

        with pytest.raises(SchemaValidationError):
            guarded_fn(VALID_INPUT, VALID_CONTEXT)

        assert side_effects == ["called"], (
            "Function body MUST execute before Phase B failure"
        )

    def test_governed_split_artifact_mode_is_split(self):
        """Successful split-enforcement artifact has enforcement_mode='split'."""
        @governed(
            policy_file=POLICY,
            role=ROLE,
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=True,
        )
        def guarded_fn(input_data, context):
            return VALID_OUTPUT

        # On success the decorator returns the output; the artifact is not
        # directly accessible.  Verify via Phase B FAIL path instead.
        # A Phase B failure attaches the artifact to the exception.
        @governed(
            policy_file=POLICY,
            role=ROLE,
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=True,
        )
        def bad_output_fn(input_data, context):
            return BAD_SCHEMA_OUTPUT

        with pytest.raises(SchemaValidationError) as exc_info:
            bad_output_fn(VALID_INPUT, VALID_CONTEXT)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["metadata"]["enforcement_mode"] == "split"


# ── Async split-enforcement tests ────────────────────────────


class TestGovernedSplitAsync:

    @pytest.mark.asyncio
    async def test_governed_split_async_blocks_function_on_phase_a_fail(self):
        """Async Phase A role failure prevents the wrapped function."""
        side_effects: list[str] = []

        @governed(
            policy_file=POLICY,
            role="unauthorized_role",
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=True,
        )
        async def guarded_fn(input_data, context):
            side_effects.append("called")
            return VALID_OUTPUT

        with pytest.raises(GovernanceViolationError):
            await guarded_fn(VALID_INPUT, VALID_CONTEXT)

        assert side_effects == [], (
            "Async function body must NOT execute when Phase A fails"
        )

    @pytest.mark.asyncio
    async def test_governed_split_async_executes_function_on_phase_a_pass(self):
        """Async Phase A passes, function runs, Phase B passes."""
        @governed(
            policy_file=POLICY,
            role=ROLE,
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=True,
        )
        async def guarded_fn(input_data, context):
            return VALID_OUTPUT

        result = await guarded_fn(VALID_INPUT, VALID_CONTEXT)
        assert result == VALID_OUTPUT


# ── Default-mode regression tests ────────────────────────────


class TestGovernedDefaultBehavior:

    def test_governed_default_mode_unchanged(self):
        """pre_call_enforcement=False (default) preserves v0.3.1 behavior."""
        @governed(
            policy_file=POLICY,
            role=ROLE,
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=False,
        )
        def guarded_fn(input_data, context):
            return VALID_OUTPUT

        result = guarded_fn(VALID_INPUT, VALID_CONTEXT)
        assert result == VALID_OUTPUT

    def test_governed_default_mode_omitted_param(self):
        """Omitting pre_call_enforcement gives same default behavior."""
        @governed(
            policy_file=POLICY,
            role=ROLE,
            model_provider=PROVIDER,
            model_identifier=MODEL,
        )
        def guarded_fn(input_data, context):
            return VALID_OUTPUT

        result = guarded_fn(VALID_INPUT, VALID_CONTEXT)
        assert result == VALID_OUTPUT

    def test_governed_argument_extraction_unchanged(self):
        """Keyword args for input_data and context still work in default mode."""
        @governed(
            policy_file=POLICY,
            role=ROLE,
            model_provider=PROVIDER,
            model_identifier=MODEL,
        )
        def guarded_fn(input_data, context):
            return VALID_OUTPUT

        result = guarded_fn(input_data=VALID_INPUT, context=VALID_CONTEXT)
        assert result == VALID_OUTPUT


# ── Edge cases ────────────────────────────────────────────────


class TestGovernedSplitEdgeCases:

    def test_governed_split_phase_a_fail_artifact_attached_to_exception(self):
        """Phase A FAIL attaches artifact with enforcement_mode='split_pre_call_only'."""
        @governed(
            policy_file=POLICY,
            role="unauthorized_role",
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=True,
        )
        def guarded_fn(input_data, context):
            return VALID_OUTPUT

        with pytest.raises(GovernanceViolationError) as exc_info:
            guarded_fn(VALID_INPUT, VALID_CONTEXT)

        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["metadata"]["enforcement_mode"] == (
            "split_pre_call_only"
        )

    def test_governed_split_function_not_called_on_phase_a_fail(self):
        """Explicit side-effect proof that function is never invoked on Phase A fail."""
        call_count = [0]

        @governed(
            policy_file=POLICY,
            role="unauthorized_role",
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=True,
        )
        def guarded_fn(input_data, context):
            call_count[0] += 1
            return VALID_OUTPUT

        with pytest.raises(GovernanceViolationError):
            guarded_fn(VALID_INPUT, VALID_CONTEXT)

        assert call_count[0] == 0, (
            "Function must not be called when Phase A fails"
        )

    def test_governed_split_preserves_function_name(self):
        """Split-mode wrapper preserves the original function name."""
        @governed(
            policy_file=POLICY,
            role=ROLE,
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=True,
        )
        def my_governed_fn(input_data, context):
            return VALID_OUTPUT

        assert my_governed_fn.__name__ == "my_governed_fn"
