from aigc import __version__, AIGC
from aigc.enforcement import enforce_invocation
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
from aigc.sinks import (
    AuditSink,
    CallbackAuditSink,
    JsonFileAuditSink,
    get_audit_sink,
    get_sink_failure_mode,
    set_audit_sink,
    set_sink_failure_mode,
)


def test_public_api_imports():
    assert callable(enforce_invocation)
    assert __version__ == "0.2.0"
    assert InvocationValidationError.__name__ == "InvocationValidationError"


def test_aigc_class_exported():
    assert AIGC is not None
    assert callable(AIGC)


def test_all_error_types_exported():
    """All error taxonomy types are importable from aigc.errors."""
    for cls in (
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
    ):
        assert issubclass(cls, AIGCError), f"{cls.__name__} not subclass of AIGCError"


def test_sink_failure_mode_apis_exported():
    """set_sink_failure_mode and get_sink_failure_mode are importable from aigc.sinks."""
    assert callable(set_sink_failure_mode)
    assert callable(get_sink_failure_mode)


def test_top_level_reexports_match_errors_module():
    """All error types are also importable from top-level aigc package."""
    import aigc

    for name in (
        "AuditSinkError",
        "ConditionResolutionError",
        "GuardEvaluationError",
        "ToolConstraintViolationError",
    ):
        assert hasattr(aigc, name), f"aigc.{name} not exported"


def test_top_level_reexports_sink_failure_mode():
    """Sink failure mode APIs importable from top-level aigc package."""
    import aigc

    assert hasattr(aigc, "set_sink_failure_mode")
    assert hasattr(aigc, "get_sink_failure_mode")
