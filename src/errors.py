"""
Custom error types for governance enforcement.
"""


class PreconditionError(Exception):
    """Raised when a precondition fails"""


class SchemaValidationError(Exception):
    """Raised on JSON schema validation failure"""


class GovernanceViolationError(Exception):
    """Raised on any violation of AIGC invariant"""
