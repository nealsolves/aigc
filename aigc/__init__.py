"""
Stable public API for the AIGC Governance SDK.
"""

import logging

from aigc.enforcement import (
    AIGC,
    PreCallResult,
    enforce_invocation,
    enforce_invocation_async,
    enforce_post_call,
    enforce_post_call_async,
    enforce_pre_call,
    enforce_pre_call_async,
)
from aigc.errors import (
    AIGCError,
    AuditSinkError,
    ConditionResolutionError,
    CustomGateViolationError,
    FeatureNotImplementedError,
    GovernanceViolationError,
    GuardEvaluationError,
    InvocationValidationError,
    PolicyLoadError,
    PolicyValidationError,
    PreconditionError,
    RiskThresholdError,
    SchemaValidationError,
    SessionStateError,
    ToolConstraintViolationError,
)
from aigc.session import GovernanceSession, SessionPreCallResult
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
from aigc.builder import InvocationBuilder
from aigc.decorators import governed
from aigc.signing import ArtifactSigner, HMACSigner, sign_artifact, verify_artifact
from aigc.gates import (
    EnforcementGate,
    GateResult,
    INSERTION_PRE_AUTHORIZATION,
    INSERTION_POST_AUTHORIZATION,
    INSERTION_PRE_OUTPUT,
    INSERTION_POST_OUTPUT,
)
from aigc.audit_chain import AuditChain, verify_chain
from aigc.lineage import AuditLineage
from aigc.provenance_gate import ProvenanceGate
from aigc.risk_history import (
    RiskHistory,
    TRAJECTORY_DEGRADING,
    TRAJECTORY_IMPROVING,
    TRAJECTORY_STABLE,
)
from aigc.policy_loader import (
    PolicyLoaderBase,
    FilePolicyLoader,
    load_policy,
    merge_policies,
    validate_policy_dates,
    COMPOSITION_INTERSECT,
    COMPOSITION_UNION,
    COMPOSITION_REPLACE,
)
from aigc.risk_scoring import (
    compute_risk_score,
    RiskScore,
    RISK_MODE_STRICT,
    RISK_MODE_RISK_SCORED,
    RISK_MODE_WARN_ONLY,
)
from aigc.policy_testing import (
    PolicyTestCase,
    PolicyTestResult,
    PolicyTestSuite,
    expect_pass,
    expect_fail,
)

# Register NullHandler so library users don't see "No handlers found" warnings.
# Host applications configure log levels and handlers on their own loggers.
logging.getLogger("aigc").addHandler(logging.NullHandler())

__version__ = "0.3.3"

__all__ = [
    "AIGC",
    "AIGCError",
    "GovernanceSession",
    "PreCallResult",
    "SessionPreCallResult",
    "SessionStateError",
    "ArtifactSigner",
    "AuditChain",
    "AuditLineage",
    "AuditSink",
    "AuditSinkError",
    "COMPOSITION_INTERSECT",
    "COMPOSITION_REPLACE",
    "COMPOSITION_UNION",
    "CallbackAuditSink",
    "ConditionResolutionError",
    "CustomGateViolationError",
    "EnforcementGate",
    "FeatureNotImplementedError",
    "FilePolicyLoader",
    "GateResult",
    "GovernanceViolationError",
    "GuardEvaluationError",
    "HMACSigner",
    "INSERTION_POST_AUTHORIZATION",
    "INSERTION_POST_OUTPUT",
    "INSERTION_PRE_AUTHORIZATION",
    "INSERTION_PRE_OUTPUT",
    "InvocationBuilder",
    "InvocationValidationError",
    "JsonFileAuditSink",
    "PolicyLoadError",
    "PolicyLoaderBase",
    "PolicyTestCase",
    "PolicyTestResult",
    "PolicyTestSuite",
    "PolicyValidationError",
    "ProvenanceGate",
    "PreconditionError",
    "RISK_MODE_RISK_SCORED",
    "RISK_MODE_STRICT",
    "RISK_MODE_WARN_ONLY",
    "RetryExhaustedError",
    "RiskHistory",
    "RiskScore",
    "RiskThresholdError",
    "SchemaValidationError",
    "ToolConstraintViolationError",
    "TRAJECTORY_DEGRADING",
    "TRAJECTORY_IMPROVING",
    "TRAJECTORY_STABLE",
    "compute_risk_score",
    "enforce_invocation",
    "enforce_invocation_async",
    "enforce_post_call",
    "enforce_post_call_async",
    "enforce_pre_call",
    "enforce_pre_call_async",
    "expect_fail",
    "expect_pass",
    "get_audit_sink",
    "get_sink_failure_mode",
    "governed",
    "load_policy",
    "merge_policies",
    "set_audit_sink",
    "set_sink_failure_mode",
    "sign_artifact",
    "validate_policy_dates",
    "verify_artifact",
    "verify_chain",
    "with_retry",
]
