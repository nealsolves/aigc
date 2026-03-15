"""
Policy testing framework for AIGC governance SDK.

Provides a small but real testing API for policy authors to validate
their policies against expected governance scenarios without running
a full application.

Usage::

    from aigc.policy_testing import PolicyTestCase, expect_pass, expect_fail

    case = PolicyTestCase(
        name="admin can generate",
        policy_file="policies/base_policy.yaml",
        invocation={
            "role": "planner",
            "model_provider": "openai",
            "model_identifier": "gpt-4",
            "input": {"prompt": "test"},
            "output": {"summary": "result"},
            "context": {"session_id": "s1"},
        },
    )

    result = case.run()
    assert result.passed
    assert "role_validation" in result.gates_evaluated
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any

from aigc._internal.enforcement import enforce_invocation
from aigc._internal.errors import AIGCError

logger = logging.getLogger("aigc.policy_testing")


@dataclass
class PolicyTestResult:
    """Result of running a policy test case."""

    name: str
    passed: bool
    enforcement_result: str  # "PASS" or "FAIL"
    audit_artifact: dict[str, Any] | None = None
    error: AIGCError | None = None
    gates_evaluated: list[str] = field(default_factory=list)
    failure_gate: str | None = None
    failure_reason: str | None = None

    @property
    def is_pass(self) -> bool:
        return self.enforcement_result == "PASS"

    @property
    def is_fail(self) -> bool:
        return self.enforcement_result == "FAIL"


@dataclass
class PolicyTestCase:
    """A single policy test scenario.

    Encapsulates a policy file, invocation data, and expected outcome.
    """

    name: str
    policy_file: str
    invocation: dict[str, Any] | None = None
    role: str = "planner"
    model_provider: str = "test-provider"
    model_identifier: str = "test-model"
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    context: dict[str, Any] | None = None

    def _build_invocation(self) -> dict[str, Any]:
        """Build a complete invocation dict from case fields."""
        if self.invocation is not None:
            inv = copy.deepcopy(self.invocation)
            inv.setdefault("policy_file", self.policy_file)
            return inv

        return {
            "policy_file": self.policy_file,
            "role": self.role,
            "model_provider": self.model_provider,
            "model_identifier": self.model_identifier,
            "input": self.input_data or {},
            "output": self.output_data or {},
            "context": self.context or {},
        }

    def run(self) -> PolicyTestResult:
        """Execute the test case and return the result.

        Does not raise on governance failures — captures them as
        FAIL results for assertion.
        """
        invocation = self._build_invocation()

        try:
            audit = enforce_invocation(invocation)
            return PolicyTestResult(
                name=self.name,
                passed=True,
                enforcement_result="PASS",
                audit_artifact=audit,
                gates_evaluated=audit.get("metadata", {}).get(
                    "gates_evaluated", []
                ),
            )
        except AIGCError as exc:
            audit = getattr(exc, "audit_artifact", None)
            return PolicyTestResult(
                name=self.name,
                passed=False,
                enforcement_result="FAIL",
                audit_artifact=audit,
                error=exc,
                gates_evaluated=(
                    audit.get("metadata", {}).get("gates_evaluated", [])
                    if audit
                    else []
                ),
                failure_gate=(
                    audit.get("failure_gate") if audit else None
                ),
                failure_reason=str(exc),
            )


def expect_pass(case: PolicyTestCase) -> PolicyTestResult:
    """Run a test case and assert it passes.

    :param case: Test case to run
    :return: PolicyTestResult
    :raises AssertionError: If enforcement result is not PASS
    """
    result = case.run()
    assert result.is_pass, (
        f"Expected PASS for '{case.name}' but got FAIL: "
        f"{result.failure_reason}"
    )
    return result


def expect_fail(
    case: PolicyTestCase,
    *,
    gate: str | None = None,
    error_type: type | None = None,
) -> PolicyTestResult:
    """Run a test case and assert it fails.

    :param case: Test case to run
    :param gate: Expected failure gate (optional)
    :param error_type: Expected error type (optional)
    :return: PolicyTestResult
    :raises AssertionError: If enforcement result is not FAIL
    """
    result = case.run()
    assert result.is_fail, (
        f"Expected FAIL for '{case.name}' but got PASS"
    )

    if gate is not None:
        assert result.failure_gate == gate, (
            f"Expected failure at gate '{gate}' but failed at "
            f"'{result.failure_gate}'"
        )

    if error_type is not None and result.error is not None:
        assert isinstance(result.error, error_type), (
            f"Expected error type {error_type.__name__} but got "
            f"{type(result.error).__name__}"
        )

    return result


class PolicyTestSuite:
    """Collection of policy test cases that can be run together.

    Usage::

        suite = PolicyTestSuite("My Policy Tests")
        suite.add(PolicyTestCase(name="test1", ...))
        suite.add(PolicyTestCase(name="test2", ...))
        results = suite.run_all()
        assert suite.all_passed(results)
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._cases: list[tuple[PolicyTestCase, str]] = []

    def add(
        self,
        case: PolicyTestCase,
        expected: str = "pass",
    ) -> None:
        """Add a test case with expected outcome.

        :param case: Test case to add
        :param expected: "pass" or "fail"
        """
        if expected not in ("pass", "fail"):
            raise ValueError(f"expected must be 'pass' or 'fail', got: {expected!r}")
        self._cases.append((case, expected))

    def run_all(self) -> list[PolicyTestResult]:
        """Run all test cases and return results."""
        results: list[PolicyTestResult] = []
        for case, expected in self._cases:
            result = case.run()
            results.append(result)
            logger.info(
                "Test '%s': expected=%s, actual=%s, match=%s",
                case.name,
                expected.upper(),
                result.enforcement_result,
                (expected == "pass") == result.is_pass,
            )
        return results

    def all_passed(self, results: list[PolicyTestResult]) -> bool:
        """Check if all test results match expectations."""
        if len(results) != len(self._cases):
            return False
        for (_, expected), result in zip(self._cases, results):
            if expected == "pass" and not result.is_pass:
                return False
            if expected == "fail" and not result.is_fail:
                return False
        return True
