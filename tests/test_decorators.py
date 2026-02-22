"""
Phase 3.4 — @governed decorator tests.

Tests: sync and async decorated functions, input/context extraction,
return value passthrough, and governance exception propagation.
"""

from __future__ import annotations

import pytest

from src.decorators import governed
from src.errors import GovernanceViolationError, SchemaValidationError

POLICY = "tests/golden_replays/golden_policy_v1.yaml"
PROVIDER = "anthropic"
MODEL = "claude-sonnet-4-5-20250929"
ROLE = "planner"

VALID_INPUT = {"task": "analyse system"}
VALID_CONTEXT = {"role_declared": True, "schema_exists": True}
VALID_OUTPUT = {"result": "analysis complete", "confidence": 0.95}
INVALID_OUTPUT = {"result": 999}  # wrong type + missing confidence


# --- Sync decorated functions ---

@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
def passing_function(input_data, context):
    return VALID_OUTPUT


@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
def failing_output_function(input_data, context):
    return INVALID_OUTPUT


def test_governed_sync_passes():
    result = passing_function(VALID_INPUT, VALID_CONTEXT)
    assert result == VALID_OUTPUT


def test_governed_sync_returns_original_output():
    result = passing_function(VALID_INPUT, VALID_CONTEXT)
    assert result is VALID_OUTPUT


def test_governed_sync_raises_on_schema_violation():
    with pytest.raises(SchemaValidationError):
        failing_output_function(VALID_INPUT, VALID_CONTEXT)


def test_governed_sync_context_as_kwarg():
    result = passing_function(VALID_INPUT, context=VALID_CONTEXT)
    assert result == VALID_OUTPUT


def test_governed_sync_bad_role_raises():
    @governed(
        policy_file=POLICY,
        role="attacker",
        model_provider=PROVIDER,
        model_identifier=MODEL,
    )
    def bad_role_fn(input_data, context):
        return VALID_OUTPUT

    with pytest.raises(GovernanceViolationError):
        bad_role_fn(VALID_INPUT, VALID_CONTEXT)


def test_governed_sync_preserves_function_name():
    assert passing_function.__name__ == "passing_function"


# --- Async decorated functions ---

@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
async def async_passing_function(input_data, context):
    return VALID_OUTPUT


@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
async def async_failing_output_function(input_data, context):
    return INVALID_OUTPUT


async def test_governed_async_passes():
    result = await async_passing_function(VALID_INPUT, VALID_CONTEXT)
    assert result == VALID_OUTPUT


async def test_governed_async_returns_original_output():
    result = await async_passing_function(VALID_INPUT, VALID_CONTEXT)
    assert result is VALID_OUTPUT


async def test_governed_async_raises_on_schema_violation():
    with pytest.raises(SchemaValidationError):
        await async_failing_output_function(VALID_INPUT, VALID_CONTEXT)


async def test_governed_async_context_as_kwarg():
    result = await async_passing_function(VALID_INPUT, context=VALID_CONTEXT)
    assert result == VALID_OUTPUT


async def test_governed_async_bad_role_raises():
    @governed(
        policy_file=POLICY,
        role="attacker",
        model_provider=PROVIDER,
        model_identifier=MODEL,
    )
    async def bad_role_async(input_data, context):
        return VALID_OUTPUT

    with pytest.raises(GovernanceViolationError):
        await bad_role_async(VALID_INPUT, VALID_CONTEXT)


async def test_governed_async_preserves_function_name():
    assert async_passing_function.__name__ == "async_passing_function"


# --- Default context ---

@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
def no_context_function(input_data):
    return VALID_OUTPUT


def test_governed_sync_no_context_defaults_to_empty():
    # Policy requires role_declared and schema_exists preconditions;
    # missing context means precondition fails — governance raises, not a crash
    with pytest.raises(Exception):
        no_context_function(VALID_INPUT)
