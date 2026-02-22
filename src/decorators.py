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
  - First positional argument is treated as ``input`` (must be a dict)
  - Second positional argument or ``context`` keyword argument is treated as
    ``context`` (must be a dict; defaults to ``{}`` if not provided)
  - Return value is treated as ``output`` (must be a dict)
  - Governance exceptions propagate unchanged from the wrapped function
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable

logger = logging.getLogger("aigc.decorators")


def governed(
    policy_file: str,
    role: str,
    model_provider: str,
    model_identifier: str,
) -> Callable:
    """
    Decorator factory that wraps a function with AIGC governance enforcement.

    The wrapped function is called first.  If it succeeds, the return value
    and call arguments are assembled into an invocation and passed through
    enforce_invocation (sync) or enforce_invocation_async (async).

    :param policy_file: Path to governance policy YAML
    :param role: Invocation role (must be declared in the policy's roles list)
    :param model_provider: Model provider identifier (e.g. "anthropic")
    :param model_identifier: Model identifier (e.g. "claude-sonnet-4-5-20250929")
    :return: Decorated function
    """
    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                input_data = args[0] if args else kwargs.get("input", {})
                context = args[1] if len(args) > 1 else kwargs.get("context", {})

                output = await fn(*args, **kwargs)

                from src.enforcement import enforce_invocation_async
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
            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                input_data = args[0] if args else kwargs.get("input", {})
                context = args[1] if len(args) > 1 else kwargs.get("context", {})

                output = fn(*args, **kwargs)

                from src.enforcement import enforce_invocation
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
