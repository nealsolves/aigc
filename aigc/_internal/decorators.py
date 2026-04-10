"""
@governed decorator for wrapping LLM call sites with governance enforcement.

Usage (sync)::

    from aigc.decorators import governed

    @governed(
        policy_file="policies/planner_policy.yaml",
        role="planner",
        model_provider="anthropic",
        model_identifier="claude-sonnet-4-5-20250929",
    )
    def plan_investigation(input_data: dict, context: dict) -> dict:
        return llm.generate(input_data)

Usage (async)::

    @governed(
        policy_file="policies/planner_policy.yaml",
        role="planner",
        model_provider="anthropic",
        model_identifier="claude-sonnet-4-5-20250929",
    )
    async def plan_investigation_async(input_data: dict, context: dict) -> dict:
        return await llm.generate_async(input_data)

Convention:
  - First positional argument is treated as ``input`` (must be a dict); keyword
    argument ``input_data`` is checked first, then ``input``, then defaults to ``{}``
  - Second positional argument or ``context`` keyword argument is treated as
    ``context`` (must be a dict; defaults to ``{}`` if not provided)
  - Return value is treated as ``output`` (must be a dict)
  - Governance exceptions propagate unchanged from the wrapped function
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import warnings
from typing import Any, Callable

logger = logging.getLogger("aigc.decorators")


def _extract_args(fn: Callable, args: tuple, kwargs: dict) -> tuple[dict, dict]:
    """Bind arguments using inspect.signature() and extract input_data and context."""
    sig = inspect.signature(fn)
    try:
        bound = sig.bind(*args, **kwargs)
    except TypeError as e:
        raise TypeError(
            f"@governed: could not bind arguments for {fn.__name__}: {e}"
        ) from e
    bound.apply_defaults()

    params = list(sig.parameters.keys())
    arguments = bound.arguments

    # Try named parameters first, then fall back to positional
    input_data: dict = {}
    if "input_data" in arguments:
        input_data = arguments["input_data"]
    elif "input" in arguments:
        input_data = arguments["input"]
    elif len(params) > 0 and params[0] in arguments:
        input_data = arguments[params[0]]

    context: dict = {}
    if "context" in arguments:
        context = arguments["context"]
    elif len(params) > 1 and params[1] != "input_data" and params[1] != "input":
        val = arguments.get(params[1])
        if isinstance(val, dict):
            context = val

    if not isinstance(input_data, dict):
        input_data = {}
    if not isinstance(context, dict):
        context = {}

    return input_data, context


def governed(
    policy_file: str,
    role: str,
    model_provider: str,
    model_identifier: str,
    *,
    pre_call_enforcement: bool = True,
) -> Callable:
    """
    Decorator factory that wraps a function with AIGC governance enforcement.

    Since v0.3.3, *pre_call_enforcement* defaults to ``True`` (split mode).

    When *pre_call_enforcement* is ``True`` (default), governance runs in two
    phases:

    * **Phase A** (pre-call): ``enforce_pre_call()`` validates policy,
      role, preconditions, guards, and tool constraints *before* the
      wrapped function executes.  If Phase A fails the function is
      **not** called.
    * **Phase B** (post-call): ``enforce_post_call()`` validates the
      function's output against schema and postconditions.

    When *pre_call_enforcement* is ``False``, the legacy unified mode is used:
    the wrapped function is called first; if it succeeds, the return value and
    call arguments are assembled into an invocation and passed through
    ``enforce_invocation``.  Passing ``False`` explicitly emits a
    ``DeprecationWarning``; this opt-out will be removed in a future release.

    :param policy_file: Path to governance policy YAML
    :param role: Invocation role (must be declared in the policy's roles list)
    :param model_provider: Model provider identifier (e.g. "anthropic")
    :param model_identifier: Model identifier (e.g. "claude-sonnet-4-5-20250929")
    :param pre_call_enforcement: If True (default), run split pre/post enforcement.
        Pass False for legacy unified mode (deprecated).
    :return: Decorated function
    """
    if pre_call_enforcement is False:
        warnings.warn(
            "@governed: pre_call_enforcement=False is deprecated. "
            "Split enforcement is the default since v0.3.3. "
            "Pass pre_call_enforcement=False only as a legacy opt-out; "
            "this option will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
    use_split_enforcement = pre_call_enforcement is not False

    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            if use_split_enforcement:
                @functools.wraps(fn)
                async def async_wrapper_split(*args: Any, **kwargs: Any) -> Any:
                    input_data, context = _extract_args(fn, args, kwargs)

                    from aigc._internal.enforcement import (
                        enforce_pre_call_async,
                        enforce_post_call_async,
                        emit_split_fn_failure_artifact,
                    )

                    pre_call_inv = {
                        "policy_file": policy_file,
                        "role": role,
                        "model_provider": model_provider,
                        "model_identifier": model_identifier,
                        "input": input_data,
                        "context": context,
                    }

                    # Phase A — raises on FAIL, blocking the wrapped function
                    pre_call_result = await enforce_pre_call_async(pre_call_inv)

                    # Function executes only after Phase A PASS
                    try:
                        output = await fn(*args, **kwargs)
                    except Exception as fn_exc:
                        emit_split_fn_failure_artifact(pre_call_result, fn_exc)
                        raise

                    # Phase B
                    await enforce_post_call_async(pre_call_result, output)
                    logger.debug(
                        "Governed split async call passed: %s", fn.__name__,
                    )
                    return output

                return async_wrapper_split
            else:
                @functools.wraps(fn)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    input_data, context = _extract_args(fn, args, kwargs)

                    output = await fn(*args, **kwargs)

                    from aigc._internal.enforcement import enforce_invocation_async
                    await enforce_invocation_async({
                        "policy_file": policy_file,
                        "role": role,
                        "model_provider": model_provider,
                        "model_identifier": model_identifier,
                        "input": input_data,
                        "output": output,
                        "context": context,
                    })
                    logger.debug("Governed async call passed: %s", fn.__name__)
                    return output

                return async_wrapper
        else:
            if use_split_enforcement:
                @functools.wraps(fn)
                def sync_wrapper_split(*args: Any, **kwargs: Any) -> Any:
                    input_data, context = _extract_args(fn, args, kwargs)

                    from aigc._internal.enforcement import (
                        enforce_pre_call,
                        enforce_post_call,
                        emit_split_fn_failure_artifact,
                    )

                    pre_call_inv = {
                        "policy_file": policy_file,
                        "role": role,
                        "model_provider": model_provider,
                        "model_identifier": model_identifier,
                        "input": input_data,
                        "context": context,
                    }

                    # Phase A — raises on FAIL, blocking the wrapped function
                    pre_call_result = enforce_pre_call(pre_call_inv)

                    # Function executes only after Phase A PASS
                    try:
                        output = fn(*args, **kwargs)
                    except Exception as fn_exc:
                        emit_split_fn_failure_artifact(pre_call_result, fn_exc)
                        raise

                    # Phase B
                    enforce_post_call(pre_call_result, output)
                    logger.debug(
                        "Governed split sync call passed: %s", fn.__name__,
                    )
                    return output

                return sync_wrapper_split
            else:
                @functools.wraps(fn)
                def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    input_data, context = _extract_args(fn, args, kwargs)

                    output = fn(*args, **kwargs)

                    from aigc._internal.enforcement import enforce_invocation
                    enforce_invocation({
                        "policy_file": policy_file,
                        "role": role,
                        "model_provider": model_provider,
                        "model_identifier": model_identifier,
                        "input": input_data,
                        "output": output,
                        "context": context,
                    })
                    logger.debug("Governed sync call passed: %s", fn.__name__)
                    return output

                return sync_wrapper

    return decorator
