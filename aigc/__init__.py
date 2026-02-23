"""
Stable public API for the AIGC Governance SDK.
"""

import logging

from aigc.enforcement import enforce_invocation, enforce_invocation_async
from aigc.errors import (
    AIGCError,
    FeatureNotImplementedError,
    GovernanceViolationError,
    InvocationValidationError,
    PolicyLoadError,
    PolicyValidationError,
    PreconditionError,
    SchemaValidationError,
)
from aigc.retry import with_retry, RetryExhaustedError
from aigc.sinks import (
    AuditSink,
    CallbackAuditSink,
    JsonFileAuditSink,
    set_audit_sink,
    get_audit_sink,
)
from aigc.decorators import governed

# Register NullHandler so library users don't see "No handlers found" warnings.
# Host applications configure log levels and handlers on their own loggers.
logging.getLogger("aigc").addHandler(logging.NullHandler())

__version__ = "0.1.2"

__all__ = [
    "AIGCError",
    "AuditSink",
    "CallbackAuditSink",
    "FeatureNotImplementedError",
    "GovernanceViolationError",
    "InvocationValidationError",
    "JsonFileAuditSink",
    "PolicyLoadError",
    "PolicyValidationError",
    "PreconditionError",
    "RetryExhaustedError",
    "SchemaValidationError",
    "enforce_invocation",
    "enforce_invocation_async",
    "get_audit_sink",
    "governed",
    "set_audit_sink",
    "with_retry",
]
