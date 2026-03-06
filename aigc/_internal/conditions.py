"""
Named condition resolution from invocation context.

Conditions are boolean flags declared in the policy and resolved
from invocation context with defaults and required enforcement.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from aigc._internal.errors import ConditionResolutionError

logger = logging.getLogger("aigc.conditions")


def resolve_conditions(
    policy: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, bool]:
    """
    Resolve named conditions from policy definitions.

    :param policy: Policy dict containing optional "conditions" block
    :param context: Invocation context with condition values
    :return: Dict mapping condition names to resolved boolean values
    :raises ConditionResolutionError: When required condition missing/invalid

    Example:
        policy = {
            "conditions": {
                "is_enterprise": {"type": "boolean", "default": False},
                "audit_enabled": {"type": "boolean", "required": True}
            }
        }
        context = {"is_enterprise": True}

        result = resolve_conditions(policy, context)
        # {"is_enterprise": True, "audit_enabled": raises error}
    """
    conditions_spec = policy.get("conditions", {})
    resolved: dict[str, bool] = {}

    for name, spec in conditions_spec.items():
        if name in context:
            # Condition value provided in context
            value = context[name]
            if not isinstance(value, bool):
                raise ConditionResolutionError(
                    f"Condition '{name}' must be boolean, got {type(value).__name__}",
                    details={"condition": name, "value_type": type(value).__name__},
                )
            resolved[name] = value
        elif "default" in spec:
            # Use default value
            default = spec["default"]
            if not isinstance(default, bool):
                raise ConditionResolutionError(
                    f"Condition '{name}' default must be boolean, got {type(default).__name__}",
                    details={"condition": name, "default_type": type(default).__name__},
                )
            resolved[name] = default
        elif spec.get("required", False):
            # Required condition missing
            available = [k for k in context if isinstance(context.get(k), bool)]
            raise ConditionResolutionError(
                f"Required condition '{name}' not found in context"
                + (f" (available boolean keys: {available})" if available else ""),
                details={
                    "condition": name,
                    "required": True,
                    "available_conditions": available,
                },
            )
        else:
            # Optional condition without default - skip with log
            logger.info(
                "Skipping optional condition '%s' (not in context, no default)",
                name,
            )

    return resolved
