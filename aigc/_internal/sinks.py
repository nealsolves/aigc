"""
Audit sink registry and built-in sink implementations.

Sinks receive every audit artifact after enforcement completes (PASS and FAIL).
Sink failure behavior is configurable: raise or log.

Note: The "queue" failure mode was deprecated in v0.3.0 and will be removed
in a future release. It now behaves identically to "log" mode.
"""

from __future__ import annotations

import abc
import copy
import json
import logging
from pathlib import Path
from typing import Any, Callable

from aigc._internal.errors import AuditSinkError

logger = logging.getLogger("aigc.sinks")

_registered_sink: AuditSink | None = None
_sink_failure_mode: str = "log"
_SENTINEL = object()  # distinguish "not passed" from explicit None


class AuditSink(abc.ABC):
    """Abstract base class for audit artifact consumers."""

    @abc.abstractmethod
    def emit(self, audit_artifact: dict[str, Any]) -> None:
        """
        Receive a completed audit artifact.

        Implementations must be synchronous.  Failures should raise exceptions
        (the registry catches them and handles per failure mode).
        """


class JsonFileAuditSink(AuditSink):
    """Appends one JSON line per audit artifact to a file (JSONL format)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def emit(self, audit_artifact: dict[str, Any]) -> None:
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(audit_artifact) + "\n")


class CallbackAuditSink(AuditSink):
    """Calls a user-provided function with each audit artifact."""

    def __init__(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._callback = callback

    def emit(self, audit_artifact: dict[str, Any]) -> None:
        self._callback(audit_artifact)


def set_audit_sink(sink: AuditSink | None) -> None:
    """
    Register the global audit sink.

    Pass ``None`` to clear the registered sink (default: no sink).
    Not thread-safe; register once at application startup.
    """
    global _registered_sink
    _registered_sink = sink


def get_audit_sink() -> AuditSink | None:
    """Return the currently registered audit sink, or None."""
    return _registered_sink


def set_sink_failure_mode(mode: str) -> None:
    """Set the global sink failure mode: 'raise' or 'log'.

    The 'queue' mode is deprecated since v0.3.0 and will be removed in
    a future release.  When 'queue' is passed, a DeprecationWarning is
    emitted and the effective mode falls back to 'log'.
    """
    import warnings

    if mode == "queue":
        warnings.warn(
            "Sink failure mode 'queue' is deprecated since v0.3.0 "
            "and will be removed in a future release. "
            "Falling back to 'log' mode.",
            DeprecationWarning,
            stacklevel=2,
        )
        mode = "log"
    if mode not in ("raise", "log"):
        raise ValueError(f"Invalid sink failure mode: {mode}")
    global _sink_failure_mode
    _sink_failure_mode = mode


def get_sink_failure_mode() -> str:
    """Return the current sink failure mode."""
    return _sink_failure_mode


def emit_to_sink(
    audit_artifact: dict[str, Any],
    *,
    sink: AuditSink | None = _SENTINEL,
    failure_mode: str | None = None,
) -> None:
    """
    Emit an audit artifact to a sink.

    The artifact is deep-copied before being handed to the sink, so sinks
    cannot mutate the caller's artifact object (Invariant C).

    :param audit_artifact: Audit artifact dict to emit
    :param sink: Explicit sink to use. When omitted (sentinel), falls back
        to the module-global ``_registered_sink``.  Pass ``None`` explicitly
        to skip emission.
    :param failure_mode: Explicit failure mode (``"raise"``/``"log"``).
        When ``None``, falls back to the module-global ``_sink_failure_mode``.
    """
    effective_sink = _registered_sink if sink is _SENTINEL else sink
    if effective_sink is None:
        return
    effective_mode = failure_mode if failure_mode is not None else _sink_failure_mode
    artifact_copy = copy.deepcopy(audit_artifact)
    try:
        effective_sink.emit(artifact_copy)
    except Exception as exc:  # noqa: BLE001
        if effective_mode == "raise":
            raise AuditSinkError(
                f"Audit sink emit failed: {exc}",
                details={"original_error": str(exc)},
            ) from exc
        logger.warning("Audit sink emit failed: %s", exc)
