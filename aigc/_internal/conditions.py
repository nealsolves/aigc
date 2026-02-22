"""
Named condition resolution from invocation context.

Conditions are boolean flags declared in the policy and resolved
from invocation context with defaults and required enforcement.
"""

from __future__ import annotations

from typing import Any, Mapping

from aigc._internal.errors import ConditionResolutionError


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
            raise ConditionResolutionError(
                f"Required condition '{name}' not found in context",
                details={"condition": name, "required": True},
            )
        # else: optional condition without default - skip

    return resolved
