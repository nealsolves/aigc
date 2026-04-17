"""
Custom error types for governance enforcement.
"""


from __future__ import annotations


class AIGCError(Exception):
    """
    Base error for governance failures.

    Supports machine-readable metadata in addition to a human-readable message.
    Audit artifacts are attached to exceptions when enforcement fails.
    """

    def __init__(self, message: str, *, code: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.audit_artifact: dict | None = None


class GovernanceViolationError(AIGCError):
    """Raised on any violation of AIGC invariant."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "GOVERNANCE_VIOLATION",
        details: dict | None = None,
    ):
        super().__init__(message, code=code, details=details)


class InvocationValidationError(GovernanceViolationError):
    """Raised when invocation payload does not match the required contract."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="INVOCATION_VALIDATION_ERROR",
            details=details,
        )


class PolicyLoadError(GovernanceViolationError):
    """Raised when policy loading/parsing fails."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message, code="POLICY_LOAD_ERROR", details=details)


class PolicyValidationError(GovernanceViolationError):
    """Raised when policy schema validation fails."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="POLICY_SCHEMA_VALIDATION_ERROR",
            details=details,
        )


class SchemaValidationError(AIGCError):
    """Raised on JSON schema validation failure."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="OUTPUT_SCHEMA_VALIDATION_ERROR",
            details=details,
        )


class PreconditionError(AIGCError):
    """Raised when a precondition fails."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="PRECONDITION_FAILED",
            details=details,
        )


class FeatureNotImplementedError(GovernanceViolationError):
    """Raised when a schema-declared feature is not yet implemented."""

    def __init__(self, feature: str):
        super().__init__(
            f"Policy feature not implemented: {feature}",
            code="FEATURE_NOT_IMPLEMENTED",
            details={"feature": feature},
        )


class ConditionResolutionError(AIGCError):
    """Raised when condition resolution fails."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="CONDITION_RESOLUTION_ERROR",
            details=details,
        )


class GuardEvaluationError(AIGCError):
    """Raised when guard evaluation fails."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="GUARD_EVALUATION_ERROR",
            details=details,
        )


class ToolConstraintViolationError(GovernanceViolationError):
    """Raised when tool constraints are violated."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="TOOL_CONSTRAINT_VIOLATION",
            details=details,
        )


class AuditSinkError(AIGCError):
    """Raised when audit sink emission fails (in 'raise' failure mode)."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="AUDIT_SINK_ERROR",
            details=details,
        )


class RiskThresholdError(AIGCError):
    """Raised when risk score exceeds threshold in strict mode."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="RISK_THRESHOLD_EXCEEDED",
            details=details,
        )


class CustomGateViolationError(GovernanceViolationError):
    """Raised when a custom enforcement gate fails.

    Distinct from GovernanceViolationError so that failure gate mapping
    can accurately classify custom gate failures without heuristic
    string matching.
    """

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="CUSTOM_GATE_VIOLATION",
            details=details,
        )


class SessionStateError(AIGCError):
    """Raised when a GovernanceSession lifecycle transition is invalid."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="WORKFLOW_INVALID_TRANSITION",
            details=details,
        )


class WorkflowStarterIntegrityError(GovernanceViolationError):
    """Raised when a generated workflow starter fails integrity validation."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="WORKFLOW_STARTER_INTEGRITY_ERROR",
            details=details,
        )
