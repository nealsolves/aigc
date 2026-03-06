"""
Audit sink registry and built-in sink implementations.

Sinks receive every audit artifact after enforcement completes (PASS and FAIL).
Sink failure behavior is configurable: raise, log, or queue.
"""

from __future__ import annotations

import abc
import json
import logging
from pathlib import Path
from typing import Any, Callable

from aigc._internal.errors import AuditSinkError

logger = logging.getLogger("aigc.sinks")

_registered_sink: AuditSink | None = None
_sink_failure_mode: str = "log"


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
    """Set the global sink failure mode: 'raise', 'log', or 'queue'."""
    if mode not in ("raise", "log", "queue"):
        raise ValueError(f"Invalid sink failure mode: {mode}")
    global _sink_failure_mode
    _sink_failure_mode = mode


def get_sink_failure_mode() -> str:
    """Return the current sink failure mode."""
    return _sink_failure_mode


def emit_to_sink(audit_artifact: dict[str, Any]) -> None:
    """
    Emit an audit artifact to the registered sink.

    If no sink is registered, this is a no-op.
    Failure behavior depends on the configured failure mode:
    - 'raise': propagate AuditSinkError
    - 'log': log warning (default, backward-compatible)
    - 'queue': log warning (queue not yet implemented)
    """
    sink = _registered_sink
    if sink is None:
        return
    try:
        sink.emit(audit_artifact)
    except Exception as exc:  # noqa: BLE001
        if _sink_failure_mode == "raise":
            raise AuditSinkError(
                f"Audit sink emit failed: {exc}",
                details={"original_error": str(exc)},
            ) from exc
        logger.warning("Audit sink emit failed: %s", exc)
