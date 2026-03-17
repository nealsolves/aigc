"""Public API wrapper for audit sink registry."""

from aigc._internal.sinks import (
    AuditSink,
    CallbackAuditSink,
    JsonFileAuditSink,
    emit_to_sink,
    get_audit_sink,
    get_sink_failure_mode,
    set_audit_sink,
    set_sink_failure_mode,
)

__all__ = [
    "AuditSink",
    "CallbackAuditSink",
    "JsonFileAuditSink",
    "emit_to_sink",
    "get_audit_sink",
    "get_sink_failure_mode",
    "set_audit_sink",
    "set_sink_failure_mode",
]
