"""
Phase 3.4 — @governed decorator tests.

Tests: sync and async decorated functions, input/context extraction,
return value passthrough, and governance exception propagation.
"""

from __future__ import annotations

import pytest

from aigc._internal.decorators import governed
from aigc._internal.errors import GovernanceViolationError, SchemaValidationError

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


# --- Kwarg capture regression (audit provenance) ---

def test_governed_sync_input_data_kwarg():
    # Keyword-style call using the documented `input_data` parameter name must
    # pass governance — not silently audit {} as the input.
    result = passing_function(input_data=VALID_INPUT, context=VALID_CONTEXT)
    assert result == VALID_OUTPUT


@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
async def async_kwarg_function(input_data, context):
    return VALID_OUTPUT


async def test_governed_async_input_data_kwarg():
    result = await async_kwarg_function(input_data=VALID_INPUT, context=VALID_CONTEXT)
    assert result == VALID_OUTPUT


# --- Reordered parameter tests (D-11 fix) ---

@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
def reordered_function(context, input_data):
    """Function with context before input_data (reversed order)."""
    return VALID_OUTPUT


def test_governed_sync_reordered_params_positional():
    result = reordered_function(VALID_CONTEXT, VALID_INPUT)
    assert result == VALID_OUTPUT


def test_governed_sync_reordered_params_kwargs():
    result = reordered_function(context=VALID_CONTEXT, input_data=VALID_INPUT)
    assert result == VALID_OUTPUT


@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
async def async_reordered_function(context, input_data):
    return VALID_OUTPUT


async def test_governed_async_reordered_params_kwargs():
    result = await async_reordered_function(context=VALID_CONTEXT, input_data=VALID_INPUT)
    assert result == VALID_OUTPUT


# --- Edge case: TypeError on bad argument binding ---

def test_governed_sync_bind_failure_raises_type_error():
    """@governed raises TypeError when called with wrong argument count."""
    @governed(
        policy_file=POLICY, role=ROLE,
        model_provider=PROVIDER, model_identifier=MODEL,
    )
    def two_args_fn(input_data, context):
        return VALID_OUTPUT

    with pytest.raises(TypeError, match="could not bind arguments"):
        two_args_fn()  # missing required args


# --- Edge case: 'input' named parameter fallback ---

@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
def input_named_param_fn(input, context):  # noqa: A002
    """Uses 'input' instead of 'input_data' as parameter name."""
    return VALID_OUTPUT


def test_governed_sync_input_param_name_fallback():
    """Functions using 'input' parameter name are correctly handled."""
    result = input_named_param_fn(VALID_INPUT, VALID_CONTEXT)
    assert result == VALID_OUTPUT


# --- Edge case: positional-only first arg as input ---

@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
def custom_named_fn(data, ctx):
    """Uses neither 'input_data', 'input', nor 'context' as param names."""
    return VALID_OUTPUT


def test_governed_sync_positional_first_arg_as_input():
    """First positional arg treated as input; second positional dict as context."""
    # 'data' is first param (falls through to positional), 'ctx' is second param
    # (not named 'input_data'/'input'/'context') but is a dict, so it becomes context
    result = custom_named_fn(VALID_INPUT, VALID_CONTEXT)
    assert result == VALID_OUTPUT


# --- Edge case: non-dict input_data coerced to {} ---

@governed(policy_file=POLICY, role=ROLE, model_provider=PROVIDER, model_identifier=MODEL)
def string_input_fn(input_data, context):
    return VALID_OUTPUT


def test_governed_sync_non_dict_input_coerced():
    """Non-dict input_data is silently coerced to {}."""
    # Passing a string as input_data — coerced to {}, governance still runs
    result = string_input_fn("not a dict", VALID_CONTEXT)
    assert result == VALID_OUTPUT


# --- Edge case: non-dict context coerced to {} ---

def test_governed_sync_non_dict_context_coerced():
    """Non-dict context is silently coerced to {}."""
    # Passing a string as context — should coerce to {} and fail on preconditions
    with pytest.raises(Exception):
        passing_function(VALID_INPUT, "not a dict")
