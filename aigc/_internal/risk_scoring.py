"""
Risk scoring engine for AIGC governance enforcement.

Provides deterministic risk scoring with three modes:
- strict: threshold breach fails closed (raises RiskThresholdError)
- risk_scored: score recorded in audit artifact without blocking
- warn_only: warning logged and recorded without blocking

Risk scores are computed from policy-defined risk factors and
recorded in audit artifact metadata for compliance evidence.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

logger = logging.getLogger("aigc.risk_scoring")

# Supported risk modes
RISK_MODE_STRICT = "strict"
RISK_MODE_RISK_SCORED = "risk_scored"
RISK_MODE_WARN_ONLY = "warn_only"
VALID_RISK_MODES = (RISK_MODE_STRICT, RISK_MODE_RISK_SCORED, RISK_MODE_WARN_ONLY)

# Default threshold for strict/risk_scored modes
DEFAULT_RISK_THRESHOLD = 0.7


class RiskScore:
    """Immutable risk score result with scoring basis evidence."""

    __slots__ = ("score", "threshold", "mode", "basis", "exceeded")

    def __init__(
        self,
        score: float,
        threshold: float,
        mode: str,
        basis: list[dict[str, Any]],
    ) -> None:
        self.score = score
        self.threshold = threshold
        self.mode = mode
        self.basis = basis
        self.exceeded = score > threshold

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for audit artifact metadata."""
        return {
            "score": self.score,
            "threshold": self.threshold,
            "mode": self.mode,
            "basis": self.basis,
            "exceeded": self.exceeded,
        }


def _compute_factor_score(
    factor: dict[str, Any],
    invocation: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute score contribution for a single risk factor.

    Each factor has:
      - name: identifier
      - weight: 0.0-1.0 contribution weight
      - condition: what triggers this factor

    Returns a basis entry with name, weight, triggered, contribution.
    """
    name = factor.get("name", "unknown")
    weight = float(factor.get("weight", 0.0))
    condition = factor.get("condition", "")

    triggered = _evaluate_risk_condition(condition, invocation, policy)
    contribution = weight if triggered else 0.0

    return {
        "name": name,
        "weight": weight,
        "triggered": triggered,
        "contribution": contribution,
    }


def _evaluate_risk_condition(
    condition: str,
    invocation: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> bool:
    """Evaluate a risk condition deterministically.

    Supported conditions:
      - "no_output_schema": true if policy lacks output_schema
      - "broad_roles": true if policy has >3 roles
      - "no_preconditions": true if policy lacks pre_conditions.required
      - "high_tool_count": true if >5 tools allowed
      - "missing_guards": true if policy lacks guards
      - "external_model": true if model_provider is not "internal"
      - any context key: true if context[key] is truthy
    """
    if condition == "no_output_schema":
        return "output_schema" not in policy
    if condition == "broad_roles":
        roles = policy.get("roles", [])
        return len(roles) > 3
    if condition == "no_preconditions":
        pre = policy.get("pre_conditions", {})
        return not pre.get("required")
    if condition == "high_tool_count":
        tools = policy.get("tools", {}).get("allowed_tools", [])
        return len(tools) > 5
    if condition == "missing_guards":
        return not policy.get("guards")
    if condition == "external_model":
        return invocation.get("model_provider", "") != "internal"
    # Fallback: check context key
    ctx = invocation.get("context", {})
    return bool(ctx.get(condition))


def compute_risk_score(
    invocation: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    risk_config: dict[str, Any] | None = None,
) -> RiskScore:
    """Compute a deterministic risk score for an invocation.

    :param invocation: The invocation being enforced
    :param policy: The loaded policy
    :param risk_config: Risk configuration from policy or runtime:
        - mode: "strict" | "risk_scored" | "warn_only"
        - threshold: float (default 0.7)
        - factors: list of {name, weight, condition}
    :return: RiskScore with score, threshold, mode, basis
    """
    if risk_config is None:
        risk_config = policy.get("risk", {})

    mode = risk_config.get("mode", RISK_MODE_STRICT)
    if mode not in VALID_RISK_MODES:
        raise ValueError(f"Invalid risk mode: {mode!r}; expected one of {VALID_RISK_MODES}")

    threshold = float(risk_config.get("threshold", DEFAULT_RISK_THRESHOLD))
    factors = risk_config.get("factors", [])

    basis: list[dict[str, Any]] = []
    total_score = 0.0

    for factor in factors:
        entry = _compute_factor_score(factor, invocation, policy)
        basis.append(entry)
        total_score += entry["contribution"]

    # Clamp score to [0.0, 1.0]
    total_score = max(0.0, min(1.0, total_score))

    result = RiskScore(
        score=total_score,
        threshold=threshold,
        mode=mode,
        basis=basis,
    )

    logger.debug(
        "Risk score computed: %.3f (threshold=%.3f, mode=%s, exceeded=%s)",
        result.score,
        result.threshold,
        result.mode,
        result.exceeded,
    )

    return result
