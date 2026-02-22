"""Public API wrapper for audit sink registry."""

from aigc._internal.sinks import (
    AuditSink,
    CallbackAuditSink,
    JsonFileAuditSink,
    emit_to_sink,
    get_audit_sink,
    set_audit_sink,
)

__all__ = [
    "AuditSink",
    "CallbackAuditSink",
    "JsonFileAuditSink",
    "emit_to_sink",
    "get_audit_sink",
    "set_audit_sink",
]
