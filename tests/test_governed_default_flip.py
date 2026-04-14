"""
PR-07 migration tests: @governed default flip to pre_call_enforcement=True.

Verifies:
1. Default (no flag) is now split enforcement — Phase A runs before fn.
2. Explicit pre_call_enforcement=True continues to work identically.
3. Explicit pre_call_enforcement=False still runs fn before governance (legacy opt-out).
4. Explicit pre_call_enforcement=False emits DeprecationWarning.
5. Async: default is also split enforcement — Phase A runs before fn.
"""

from __future__ import annotations

import warnings

import pytest

from aigc._internal.decorators import governed
from aigc._internal.errors import GovernanceViolationError

POLICY = "tests/golden_replays/golden_policy_v1.yaml"
PROVIDER = "anthropic"
MODEL = "claude-sonnet-4-5-20250929"
ROLE = "planner"

VALID_INPUT = {"task": "analyse system"}
VALID_CONTEXT = {"role_declared": True, "schema_exists": True}
VALID_OUTPUT = {"result": "analysis complete", "confidence": 0.95}


def test_default_is_split_enforcement_sync():
    """Without the flag, Phase A runs before fn; bad role blocks fn execution."""
    side_effects: list[str] = []

    @governed(
        policy_file=POLICY,
        role="unauthorized_role",
        model_provider=PROVIDER,
        model_identifier=MODEL,
    )
    def guarded_fn(input_data, context):
        side_effects.append("called")
        return VALID_OUTPUT

    with pytest.raises(GovernanceViolationError):
        guarded_fn(VALID_INPUT, VALID_CONTEXT)

    assert side_effects == [], (
        "Default mode must run Phase A before fn; Phase A failure must block fn"
    )


def test_explicit_true_unchanged():
    """Explicit pre_call_enforcement=True still produces the same result as before."""
    @governed(
        policy_file=POLICY,
        role=ROLE,
        model_provider=PROVIDER,
        model_identifier=MODEL,
        pre_call_enforcement=True,
    )
    def fn(input_data, context):
        return VALID_OUTPUT

    result = fn(VALID_INPUT, VALID_CONTEXT)
    assert result == VALID_OUTPUT


def test_explicit_false_preserves_legacy_behavior():
    """pre_call_enforcement=False still calls fn before governance (legacy unified mode)."""
    side_effects: list[str] = []

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)

        @governed(
            policy_file=POLICY,
            role="unauthorized_role",
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=False,
        )
        def legacy_fn(input_data, context):
            side_effects.append("called")
            return VALID_OUTPUT

    with pytest.raises(GovernanceViolationError):
        legacy_fn(VALID_INPUT, VALID_CONTEXT)

    assert side_effects == ["called"], (
        "Legacy mode must call fn before governance validates role"
    )


def test_explicit_false_emits_deprecation_warning():
    """pre_call_enforcement=False emits DeprecationWarning at decoration time."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        @governed(
            policy_file=POLICY,
            role=ROLE,
            model_provider=PROVIDER,
            model_identifier=MODEL,
            pre_call_enforcement=False,
        )
        def fn(input_data, context):
            return VALID_OUTPUT

    deprecation_warnings = [
        x for x in w if issubclass(x.category, DeprecationWarning)
    ]
    assert len(deprecation_warnings) == 1
    assert "pre_call_enforcement=False" in str(deprecation_warnings[0].message)


@pytest.mark.asyncio
async def test_async_default_is_split_enforcement():
    """Async: default mode (no flag) runs Phase A before fn."""
    side_effects: list[str] = []

    @governed(
        policy_file=POLICY,
        role="unauthorized_role",
        model_provider=PROVIDER,
        model_identifier=MODEL,
    )
    async def async_fn(input_data, context):
        side_effects.append("called")
        return VALID_OUTPUT

    with pytest.raises(GovernanceViolationError):
        await async_fn(VALID_INPUT, VALID_CONTEXT)

    assert side_effects == [], (
        "Async default mode must run Phase A before fn"
    )
