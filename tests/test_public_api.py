import aigc
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
    assert __version__ == "0.3.2"
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
    for name in (
        "AuditSinkError",
        "ConditionResolutionError",
        "GuardEvaluationError",
        "ToolConstraintViolationError",
    ):
        assert hasattr(aigc, name), f"aigc.{name} not exported"


def test_top_level_reexports_sink_failure_mode():
    """Sink failure mode APIs importable from top-level aigc package."""
    assert hasattr(aigc, "set_sink_failure_mode")
    assert hasattr(aigc, "get_sink_failure_mode")


def test_m2_risk_scoring_exports():
    """Risk scoring symbols are importable from top-level aigc package."""
    from aigc import (
        compute_risk_score,
        RiskScore,
        RISK_MODE_STRICT,
        RISK_MODE_RISK_SCORED,
        RISK_MODE_WARN_ONLY,
    )
    assert callable(compute_risk_score)
    assert RiskScore is not None
    assert isinstance(RISK_MODE_STRICT, str)
    assert isinstance(RISK_MODE_RISK_SCORED, str)
    assert isinstance(RISK_MODE_WARN_ONLY, str)


def test_m2_signing_exports():
    """Signing functions are importable from top-level aigc package."""
    from aigc import sign_artifact, verify_artifact
    assert callable(sign_artifact)
    assert callable(verify_artifact)


def test_m2_policy_testing_exports():
    """Policy testing framework is importable from top-level aigc package."""
    from aigc import (
        PolicyTestCase,
        PolicyTestResult,
        PolicyTestSuite,
        expect_pass,
        expect_fail,
    )
    assert PolicyTestCase is not None
    assert PolicyTestResult is not None
    assert PolicyTestSuite is not None
    assert callable(expect_pass)
    assert callable(expect_fail)


def test_m2_audit_chain_exports():
    """Audit chain symbols are importable from top-level aigc package."""
    from aigc import AuditChain, verify_chain
    assert AuditChain is not None
    assert callable(verify_chain)


def test_m2_policy_loader_exports():
    """Policy loader functions and constants importable from top-level aigc package."""
    from aigc import (
        load_policy,
        merge_policies,
        validate_policy_dates,
        COMPOSITION_INTERSECT,
        COMPOSITION_UNION,
        COMPOSITION_REPLACE,
    )
    assert callable(load_policy)
    assert callable(merge_policies)
    assert callable(validate_policy_dates)
    assert isinstance(COMPOSITION_INTERSECT, str)
    assert isinstance(COMPOSITION_UNION, str)
    assert isinstance(COMPOSITION_REPLACE, str)


def test_m2_gate_insertion_point_exports():
    """Gate insertion point constants importable from top-level aigc package."""
    from aigc import (
        INSERTION_PRE_AUTHORIZATION,
        INSERTION_POST_AUTHORIZATION,
        INSERTION_PRE_OUTPUT,
        INSERTION_POST_OUTPUT,
    )
    assert isinstance(INSERTION_PRE_AUTHORIZATION, str)
    assert isinstance(INSERTION_POST_AUTHORIZATION, str)
    assert isinstance(INSERTION_PRE_OUTPUT, str)
    assert isinstance(INSERTION_POST_OUTPUT, str)


def test_audit_reexport_stub():
    """All symbols in aigc.audit are importable from the public path."""
    from aigc.audit import (
        AUDIT_SCHEMA_VERSION,
        POLICY_SCHEMA_VERSION,
        checksum,
        generate_audit_artifact,
    )
    assert isinstance(AUDIT_SCHEMA_VERSION, str)
    assert isinstance(POLICY_SCHEMA_VERSION, str)
    assert callable(checksum)
    assert callable(generate_audit_artifact)


def test_validator_reexport_stub():
    """All symbols in aigc.validator are importable from the public path."""
    from aigc.validator import (
        validate_postconditions,
        validate_preconditions,
        validate_role,
        validate_schema,
    )
    assert callable(validate_postconditions)
    assert callable(validate_preconditions)
    assert callable(validate_role)
    assert callable(validate_schema)


def test_telemetry_reexport_stub():
    """aigc.telemetry re-export is importable from the public path."""
    from aigc.telemetry import is_otel_available
    assert callable(is_otel_available)


def test_split_enforcement_exports():
    """Split enforcement symbols are importable from top-level aigc package."""
    from aigc import (
        PreCallResult,
        enforce_pre_call,
        enforce_post_call,
        enforce_pre_call_async,
        enforce_post_call_async,
    )
    assert PreCallResult is not None
    assert callable(enforce_pre_call)
    assert callable(enforce_post_call)
    assert callable(enforce_pre_call_async)
    assert callable(enforce_post_call_async)


def test_split_enforcement_top_level_hasattr():
    """Split enforcement symbols accessible via hasattr on aigc."""
    for name in (
        "PreCallResult",
        "enforce_pre_call",
        "enforce_post_call",
        "enforce_pre_call_async",
        "enforce_post_call_async",
    ):
        assert hasattr(aigc, name), f"aigc.{name} not exported"


def test_all_list_completeness():
    """__all__ contains every M2 symbol that should be public."""
    expected_m2_symbols = {
        "compute_risk_score", "RiskScore",
        "RISK_MODE_STRICT", "RISK_MODE_RISK_SCORED", "RISK_MODE_WARN_ONLY",
        "sign_artifact", "verify_artifact",
        "PolicyTestCase", "PolicyTestResult", "PolicyTestSuite",
        "expect_pass", "expect_fail",
        "verify_chain",
        "load_policy", "merge_policies", "validate_policy_dates",
        "COMPOSITION_INTERSECT", "COMPOSITION_UNION", "COMPOSITION_REPLACE",
        "INSERTION_PRE_AUTHORIZATION", "INSERTION_POST_AUTHORIZATION",
        "INSERTION_PRE_OUTPUT", "INSERTION_POST_OUTPUT",
    }
    all_set = set(aigc.__all__)
    missing = expected_m2_symbols - all_set
    assert not missing, f"Missing from __all__: {sorted(missing)}"
