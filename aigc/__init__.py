"""
Stable public API for the AIGC Governance SDK.
"""

import logging

from aigc.enforcement import enforce_invocation, enforce_invocation_async, AIGC
from aigc.errors import (
    AIGCError,
    AuditSinkError,
    ConditionResolutionError,
    FeatureNotImplementedError,
    GovernanceViolationError,
    GuardEvaluationError,
    InvocationValidationError,
    PolicyLoadError,
    PolicyValidationError,
    PreconditionError,
    SchemaValidationError,
    ToolConstraintViolationError,
)
from aigc.retry import with_retry, RetryExhaustedError
from aigc.sinks import (
    AuditSink,
    CallbackAuditSink,
    JsonFileAuditSink,
    get_audit_sink,
    get_sink_failure_mode,
    set_audit_sink,
    set_sink_failure_mode,
)
from aigc.decorators import governed

# Register NullHandler so library users don't see "No handlers found" warnings.
# Host applications configure log levels and handlers on their own loggers.
logging.getLogger("aigc").addHandler(logging.NullHandler())

__version__ = "0.1.3"

__all__ = [
    "AIGC",
    "AIGCError",
    "AuditSink",
    "AuditSinkError",
    "CallbackAuditSink",
    "ConditionResolutionError",
    "FeatureNotImplementedError",
    "GovernanceViolationError",
    "GuardEvaluationError",
    "InvocationValidationError",
    "JsonFileAuditSink",
    "PolicyLoadError",
    "PolicyValidationError",
    "PreconditionError",
    "RetryExhaustedError",
    "SchemaValidationError",
    "ToolConstraintViolationError",
    "enforce_invocation",
    "enforce_invocation_async",
    "get_audit_sink",
    "get_sink_failure_mode",
    "governed",
    "set_audit_sink",
    "set_sink_failure_mode",
    "with_retry",
]
