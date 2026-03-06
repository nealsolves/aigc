"""Tests for strict mode enforcement (WS-13)."""

import warnings

import pytest

from aigc import AIGC
from aigc._internal.enforcement import _validate_policy_strict
from aigc._internal.errors import PolicyValidationError


POLICY = "tests/golden_replays/golden_policy_v1.yaml"
TYPED_POLICY = "tests/fixtures/typed_preconditions_policy.yaml"
NO_PRECONDITIONS_POLICY = "tests/fixtures/no_preconditions_policy.yaml"


def _make_invocation(policy_file=POLICY):
    return {
        "policy_file": policy_file,
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4-5-20250929",
        "role": "planner",
        "input": {"task": "analyse"},
        "output": {"result": "ok", "confidence": 0.9},
        "context": {"role_declared": True, "schema_exists": True},
    }


# --- Unit tests for _validate_policy_strict ---


def test_strict_rejects_no_roles_unit():
    """Strict mode rejects policy dict without roles."""
    policy = {"roles": [], "pre_conditions": {"required": {"k": {"type": "string"}}}}
    with pytest.raises(PolicyValidationError) as exc_info:
        _validate_policy_strict(policy, strict_mode=True)
    assert any("roles" in i for i in exc_info.value.details["issues"])


def test_strict_rejects_no_preconditions_unit():
    """Strict mode rejects policy dict without preconditions."""
    policy = {"roles": ["planner"]}
    with pytest.raises(PolicyValidationError) as exc_info:
        _validate_policy_strict(policy, strict_mode=True)
    assert any("pre_conditions" in i for i in exc_info.value.details["issues"])


def test_strict_rejects_bare_string_preconditions_unit():
    """Strict mode rejects bare-string (list) preconditions."""
    policy = {"roles": ["planner"], "pre_conditions": {"required": ["key1"]}}
    with pytest.raises(PolicyValidationError) as exc_info:
        _validate_policy_strict(policy, strict_mode=True)
    assert any("bare-string" in i for i in exc_info.value.details["issues"])


def test_strict_passes_valid_typed_policy_unit():
    """Strict mode accepts well-formed typed policy dict."""
    policy = {"roles": ["planner"], "pre_conditions": {"required": {"k": {"type": "string"}}}}
    _validate_policy_strict(policy, strict_mode=True)  # Should not raise


def test_strict_collects_multiple_issues():
    """Strict mode reports all issues, not just the first."""
    policy = {"roles": []}  # no roles AND no preconditions
    with pytest.raises(PolicyValidationError) as exc_info:
        _validate_policy_strict(policy, strict_mode=True)
    issues = exc_info.value.details["issues"]
    assert len(issues) == 2


# --- Integration: strict mode via AIGC.enforce() ---


def test_strict_rejects_bare_string_preconditions_e2e():
    """AIGC(strict_mode=True) rejects golden policy with bare-string preconditions."""
    aigc = AIGC(strict_mode=True)
    inv = _make_invocation(POLICY)
    with pytest.raises(PolicyValidationError) as exc_info:
        aigc.enforce(inv)
    assert any("bare-string" in i for i in exc_info.value.details["issues"])


def test_strict_rejects_no_preconditions_e2e():
    """AIGC(strict_mode=True) rejects policy without preconditions."""
    aigc = AIGC(strict_mode=True)
    inv = _make_invocation(NO_PRECONDITIONS_POLICY)
    with pytest.raises(PolicyValidationError) as exc_info:
        aigc.enforce(inv)
    assert any("pre_conditions" in i for i in exc_info.value.details["issues"])


def test_strict_passes_typed_policy_e2e():
    """AIGC(strict_mode=True) accepts typed precondition policy."""
    aigc = AIGC(strict_mode=True)
    inv = _make_invocation(TYPED_POLICY)
    audit = aigc.enforce(inv)
    assert audit["enforcement_result"] == "PASS"


# --- Non-strict mode warns but doesn't raise ---


def test_nonstrict_warns_bare_string():
    """Non-strict AIGC warns for bare-string preconditions but proceeds."""
    aigc = AIGC(strict_mode=False)
    inv = _make_invocation(POLICY)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        audit = aigc.enforce(inv)
    assert audit["enforcement_result"] == "PASS"


def test_nonstrict_warns_no_preconditions():
    """Non-strict AIGC warns for missing preconditions."""
    aigc = AIGC(strict_mode=False)
    inv = _make_invocation(NO_PRECONDITIONS_POLICY)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        audit = aigc.enforce(inv)
    assert audit["enforcement_result"] == "PASS"
    user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
    assert any("pre_conditions" in str(x.message) for x in user_warnings)


# --- Standalone enforce_invocation unaffected ---


def test_standalone_enforce_unaffected():
    """Standalone enforce_invocation() does not enforce strict mode."""
    from aigc import enforce_invocation

    inv = _make_invocation(POLICY)
    audit = enforce_invocation(inv)
    assert audit["enforcement_result"] == "PASS"
