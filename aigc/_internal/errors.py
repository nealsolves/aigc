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


class WorkflowApprovalRequiredError(GovernanceViolationError):
    """Raised or reported when a workflow step requires human approval."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="WORKFLOW_APPROVAL_REQUIRED",
            details=details,
        )


class WorkflowStepBudgetExceededError(GovernanceViolationError):
    """Raised when a session exceeds its max_steps budget."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="WORKFLOW_STEP_BUDGET_EXCEEDED",
            details=details,
        )


class WorkflowHookDeniedError(GovernanceViolationError):
    """Raised when a ValidatorHook returns DENY or times out."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="WORKFLOW_HOOK_DENIED",
            details=details,
        )


class WorkflowSourceRequiredError(GovernanceViolationError):
    """Raised or reported when source IDs are required but not provided."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="WORKFLOW_SOURCE_REQUIRED",
            details=details,
        )


class WorkflowToolBudgetExceededError(GovernanceViolationError):
    """Raised or reported when tool call budget is exceeded."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="WORKFLOW_TOOL_BUDGET_EXCEEDED",
            details=details,
        )


class WorkflowUnsupportedBindingError(GovernanceViolationError):
    """Raised or reported when an unsupported protocol binding is detected."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="WORKFLOW_UNSUPPORTED_BINDING",
            details=details,
        )


class WorkflowSessionTokenInvalidError(AIGCError):
    """Raised or reported when a session token is malformed, stale, or replayed."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            message,
            code="WORKFLOW_SESSION_TOKEN_INVALID",
            details=details,
        )


class WorkflowParticipantMismatchError(GovernanceViolationError):
    """Raised when a step's participant_id is missing or not in the declared participants list."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message, code="WORKFLOW_PARTICIPANT_MISMATCH", details=details)


class WorkflowSequenceViolationError(GovernanceViolationError):
    """Raised when a step violates the required_sequence order."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message, code="WORKFLOW_SEQUENCE_VIOLATION", details=details)


class WorkflowTransitionDeniedError(GovernanceViolationError):
    """Raised when a step transition is not in the allowed_transitions map."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message, code="WORKFLOW_TRANSITION_DENIED", details=details)


class WorkflowRoleViolationError(GovernanceViolationError):
    """Raised when a step's role is not in allowed_agent_roles."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message, code="WORKFLOW_ROLE_VIOLATION", details=details)


class WorkflowProtocolViolationError(GovernanceViolationError):
    """Raised when a step's protocol evidence fails protocol_constraints."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message, code="WORKFLOW_PROTOCOL_VIOLATION", details=details)


class WorkflowHandoffDeniedError(GovernanceViolationError):
    """Raised when a participant handoff pair is not in the allowed handoffs list."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message, code="WORKFLOW_HANDOFF_DENIED", details=details)
