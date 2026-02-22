"""
Guard evaluation engine for conditional policy expansion.

Guards use when/then rules to expand the effective policy based on
runtime context. Guard effects are additive and processed in order.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from aigc._internal.conditions import resolve_conditions
from aigc._internal.errors import GuardEvaluationError


def _merge_policy_blocks(base: dict[str, Any], overlay: Mapping[str, Any]) -> None:
    """
    Merge overlay into base dict (in-place, additive semantics).

    Rules:
    - Arrays: append overlay items to base array
    - Dicts: recursive merge
    - Scalars: overlay replaces base

    :param base: Base dict to merge into (modified in-place)
    :param overlay: Overlay dict to merge from
    """
    for key, value in overlay.items():
        if key not in base:
            base[key] = copy.deepcopy(value)
        elif isinstance(base[key], list) and isinstance(value, list):
            base[key].extend(copy.deepcopy(value))
        elif isinstance(base[key], dict) and isinstance(value, dict):
            _merge_policy_blocks(base[key], value)
        else:
            # Scalar replacement
            base[key] = copy.deepcopy(value)


def _evaluate_condition_expression(
    expr: str,
    resolved_conditions: Mapping[str, bool],
    invocation: Mapping[str, Any],
) -> bool:
    """
    Evaluate a guard condition expression.

    Supported expressions:
    - Boolean lookup: "is_enterprise" -> resolved_conditions["is_enterprise"]
    - Equality: "role == verifier" -> invocation["role"] == "verifier"

    :param expr: Condition expression string
    :param resolved_conditions: Pre-resolved named conditions
    :param invocation: Full invocation dict (for role checks)
    :return: Boolean result
    :raises GuardEvaluationError: On unknown condition or unsupported expression
    """
    expr = expr.strip()

    # Equality check: "role == verifier"
    if " == " in expr:
        left, right = expr.split(" == ", 1)
        left = left.strip()
        right = right.strip().strip('"\'')

        if left == "role":
            return invocation.get("role") == right
        raise GuardEvaluationError(
            f"Unsupported equality expression: {expr}",
            details={"expression": expr, "left": left},
        )

    # Boolean lookup: "is_enterprise"
    if expr in resolved_conditions:
        return resolved_conditions[expr]

    raise GuardEvaluationError(
        f"Unknown condition in guard expression: {expr}",
        details={
            "expression": expr,
            "available_conditions": list(resolved_conditions.keys()),
        },
    )


def evaluate_guards(
    policy: Mapping[str, Any],
    context: Mapping[str, Any],
    invocation: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, bool]]:
    """
    Evaluate guards and produce effective policy.

    :param policy: Original policy dict
    :param context: Invocation context
    :param invocation: Full invocation (for role checks in guard conditions)
    :return: Tuple of (effective_policy, guards_evaluated, conditions_resolved)

    guards_evaluated format:
        [{"condition": "is_enterprise", "matched": True}, ...]

    conditions_resolved format:
        {"is_enterprise": True, "audit_enabled": False}
    """
    guards = policy.get("guards", [])

    # Resolve conditions first (even if no guards, for audit metadata)
    resolved_conditions = resolve_conditions(policy, context)

    if not guards:
        return dict(policy), [], resolved_conditions

    # Start with copy of original policy
    effective_policy = copy.deepcopy(dict(policy))
    guards_evaluated: list[dict[str, Any]] = []

    # Process guards in declaration order
    for guard in guards:
        when_clause = guard.get("when", {})
        condition_expr = when_clause.get("condition", "")

        try:
            matched = _evaluate_condition_expression(
                condition_expr, resolved_conditions, invocation
            )
        except GuardEvaluationError:
            # Re-raise evaluation errors
            raise

        guards_evaluated.append(
            {
                "condition": condition_expr,
                "matched": matched,
            }
        )

        if matched:
            then_clause = guard.get("then", {})
            _merge_policy_blocks(effective_policy, then_clause)

    return effective_policy, guards_evaluated, resolved_conditions
