"""Tests for InvocationBuilder (WS-16)."""

import pytest

from aigc import InvocationBuilder
from aigc._internal.errors import InvocationValidationError


POLICY = "tests/golden_replays/golden_policy_v1.yaml"


def test_builder_produces_valid_invocation():
    """Builder produces a dict that passes enforcement."""
    from aigc import enforce_invocation

    inv = (
        InvocationBuilder()
        .policy(POLICY)
        .model("anthropic", "claude-sonnet-4-5-20250929")
        .role("planner")
        .input({"task": "analyse"})
        .output({"result": "ok", "confidence": 0.9})
        .context({"role_declared": True, "schema_exists": True})
        .build()
    )
    audit = enforce_invocation(inv)
    assert audit["enforcement_result"] == "PASS"


def test_builder_missing_field_raises():
    """build() without required fields raises InvocationValidationError."""
    builder = InvocationBuilder().policy(POLICY).role("planner")
    with pytest.raises(InvocationValidationError):
        builder.build()


def test_builder_method_chaining():
    """All setter methods return the builder instance."""
    builder = InvocationBuilder()
    assert builder.policy(POLICY) is builder
    assert builder.model("anthropic", "claude-sonnet-4-5-20250929") is builder
    assert builder.role("planner") is builder
    assert builder.input({"task": "x"}) is builder
    assert builder.output({"result": "y"}) is builder
    assert builder.context({"role_declared": True}) is builder
    assert builder.tools([]) is builder


def test_builder_produces_independent_dicts():
    """Two build() calls produce independent dicts."""
    builder = (
        InvocationBuilder()
        .policy(POLICY)
        .model("anthropic", "claude-sonnet-4-5-20250929")
        .role("planner")
        .input({"task": "analyse"})
        .output({"result": "ok", "confidence": 0.9})
        .context({"role_declared": True, "schema_exists": True})
    )
    d1 = builder.build()
    d2 = builder.build()
    assert d1 == d2
    assert d1 is not d2


def test_builder_exported_from_top_level():
    """InvocationBuilder is importable from top-level aigc package."""
    import aigc
    assert hasattr(aigc, "InvocationBuilder")
    assert aigc.InvocationBuilder is InvocationBuilder
