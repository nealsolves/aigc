"""Tests for the policy testing framework (M2 feature)."""
import pytest

from aigc._internal.policy_testing import (
    PolicyTestCase,
    PolicyTestResult,
    PolicyTestSuite,
    expect_pass,
    expect_fail,
)
from aigc._internal.errors import GovernanceViolationError


POLICY_FILE = "policies/base_policy.yaml"


def _passing_case():
    return PolicyTestCase(
        name="passing case",
        policy_file=POLICY_FILE,
        role="planner",
        input_data={"prompt": "test"},
        output_data={"result": "ok"},
        context={"role_declared": True, "schema_exists": True},
    )


def _failing_case():
    return PolicyTestCase(
        name="failing case (bad role)",
        policy_file=POLICY_FILE,
        role="unauthorized_role",
        input_data={"prompt": "test"},
        output_data={"result": "ok"},
        context={"role_declared": True, "schema_exists": True},
    )


# ── PolicyTestCase.run() ────────────────────────────────────────


def test_passing_case_run():
    result = _passing_case().run()
    assert result.passed
    assert result.is_pass
    assert not result.is_fail
    assert result.enforcement_result == "PASS"
    assert result.audit_artifact is not None
    assert len(result.gates_evaluated) > 0


def test_failing_case_run():
    result = _failing_case().run()
    assert not result.passed
    assert result.is_fail
    assert not result.is_pass
    assert result.enforcement_result == "FAIL"
    assert result.error is not None
    assert result.failure_gate == "role_validation"


def test_case_with_full_invocation():
    case = PolicyTestCase(
        name="full invocation",
        policy_file=POLICY_FILE,
        invocation={
            "policy_file": POLICY_FILE,
            "model_provider": "test",
            "model_identifier": "model",
            "role": "planner",
            "input": {},
            "output": {"result": "ok"},
            "context": {"role_declared": True, "schema_exists": True},
        },
    )
    result = case.run()
    assert result.is_pass


# ── expect_pass / expect_fail ────────────────────────────────────


def test_expect_pass_on_passing():
    result = expect_pass(_passing_case())
    assert result.is_pass


def test_expect_pass_on_failing():
    with pytest.raises(AssertionError, match="Expected PASS"):
        expect_pass(_failing_case())


def test_expect_fail_on_failing():
    result = expect_fail(_failing_case())
    assert result.is_fail


def test_expect_fail_on_passing():
    with pytest.raises(AssertionError, match="Expected FAIL"):
        expect_fail(_passing_case())


def test_expect_fail_with_gate():
    result = expect_fail(_failing_case(), gate="role_validation")
    assert result.failure_gate == "role_validation"


def test_expect_fail_wrong_gate():
    with pytest.raises(AssertionError, match="Expected failure at gate"):
        expect_fail(_failing_case(), gate="schema_validation")


def test_expect_fail_with_error_type():
    result = expect_fail(
        _failing_case(),
        error_type=GovernanceViolationError,
    )
    assert isinstance(result.error, GovernanceViolationError)


# ── PolicyTestSuite ──────────────────────────────────────────────


def test_suite_run_all():
    suite = PolicyTestSuite("test suite")
    suite.add(_passing_case(), expected="pass")
    suite.add(_failing_case(), expected="fail")

    results = suite.run_all()
    assert len(results) == 2
    assert suite.all_passed(results)


def test_suite_detects_mismatch():
    suite = PolicyTestSuite("mismatch suite")
    suite.add(_passing_case(), expected="fail")  # Wrong expectation

    results = suite.run_all()
    assert not suite.all_passed(results)


def test_suite_invalid_expected():
    suite = PolicyTestSuite("bad suite")
    with pytest.raises(ValueError, match="pass.*fail"):
        suite.add(_passing_case(), expected="maybe")


# ── Result properties ────────────────────────────────────────────


def test_result_gates_populated():
    result = _passing_case().run()
    assert "guard_evaluation" in result.gates_evaluated
    assert "role_validation" in result.gates_evaluated


def test_result_name_preserved():
    result = _passing_case().run()
    assert result.name == "passing case"
