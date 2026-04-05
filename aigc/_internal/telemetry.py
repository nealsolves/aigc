"""
OpenTelemetry integration for AIGC governance enforcement.

Provides optional instrumentation that adds spans and attributes around
enforcement gates. When OpenTelemetry is not installed, all operations
are no-ops — governance behavior is never affected by telemetry state.

Instrumentation must not weaken determinism of governance outcomes.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Generator

logger = logging.getLogger("aigc.telemetry")

# Try to import OpenTelemetry; fall back to no-ops if unavailable.
_otel_available = False
_tracer = None

try:
    from opentelemetry import trace  # type: ignore[import-untyped]
    _otel_available = True
    _tracer = trace.get_tracer("aigc.enforcement")
except ImportError:
    pass


def is_otel_available() -> bool:
    """Return True if OpenTelemetry is importable."""
    return _otel_available


@contextlib.contextmanager
def enforcement_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Context manager that creates an OTel span if available.

    If OpenTelemetry is not installed, yields None (no-op).
    Governance logic must not depend on the span object.

    :param name: Span name (e.g. "aigc.enforce_invocation")
    :param attributes: Optional span attributes
    """
    if not _otel_available or _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(name, attributes=attributes or {}) as span:
        yield span


def record_gate_event(
    span: Any,
    gate_id: str,
    *,
    status: str = "completed",
    details: dict[str, Any] | None = None,
) -> None:
    """Record a gate execution event on an OTel span.

    No-op if span is None (OTel not available).

    :param span: Active OTel span (or None)
    :param gate_id: Gate identifier
    :param status: Gate status ("completed" or "failed")
    :param details: Optional detail attributes
    """
    if span is None:
        return

    try:
        span.set_attribute(f"aigc.gate.{gate_id}.status", status)
        if details:
            for k, v in details.items():
                if isinstance(v, (str, int, float, bool)):
                    span.set_attribute(f"aigc.gate.{gate_id}.{k}", v)
    except Exception:  # noqa: BLE001
        # Never let telemetry failures affect governance
        logger.debug("Failed to record gate event for %s", gate_id)


def record_enforcement_result(
    span: Any,
    result: str,
    *,
    policy_file: str | None = None,
    role: str | None = None,
    risk_score: float | None = None,
    enforcement_mode: str | None = None,
) -> None:
    """Record enforcement result attributes on an OTel span.

    :param span: Active OTel span (or None)
    :param result: "PASS" or "FAIL"
    :param policy_file: Policy file path
    :param role: Invocation role
    :param risk_score: Computed risk score
    :param enforcement_mode: "unified" or "split"
    """
    if span is None:
        return

    try:
        span.set_attribute("aigc.enforcement.result", result)
        if policy_file:
            span.set_attribute("aigc.enforcement.policy_file", policy_file)
        if role:
            span.set_attribute("aigc.enforcement.role", role)
        if risk_score is not None:
            span.set_attribute("aigc.enforcement.risk_score", risk_score)
        if enforcement_mode is not None:
            span.set_attribute("aigc.enforcement_mode", enforcement_mode)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to record enforcement result")
