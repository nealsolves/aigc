"""Regression tests for RELEASE_0.3.2_IMPLEMENTATION_AUDIT_2026-04-04.md findings.

F-5  — Non-mapping invocations raise but omit FAIL artifact
F-6  — README test count stale (no test; manual)
F-4  — FAIL artifact identity forgeable via _frozen_invocation_snapshot mutation
F-1  — Phase B policy tampering via _frozen_policy_bytes replacement
F-2  — Phase B gate bypass via _phase_b_grouped_gates object.__setattr__ replacement
F-3  — Clone replay: deepcopy/pickle of unconsumed token allows both to PASS
"""
from __future__ import annotations

import copy
import json
import pickle
import types

import pytest

from aigc._internal.enforcement import (
    AIGC,
    PreCallResult,
    enforce_invocation,
    enforce_post_call,
    enforce_pre_call,
    enforce_pre_call_async,
)
from aigc._internal.errors import InvocationValidationError
from aigc._internal.gates import EnforcementGate, GateResult

GOLDEN_POLICY = "tests/golden_replays/golden_policy_v1.yaml"
INSERTION_PRE_OUTPUT = "pre_output"


def _pre_call_inv(**overrides):
    inv = {
        "policy_file": GOLDEN_POLICY,
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4-5-20250929",
        "role": "planner",
        "input": {"query": "test"},
        "context": {"role_declared": True, "schema_exists": True},
    }
    inv.update(overrides)
    return inv


def _full_inv(output=None, **overrides):
    inv = _pre_call_inv(**overrides)
    inv["output"] = output if output is not None else {"result": "ok", "confidence": 0.9}
    return inv


def _valid_output():
    return {"result": "ok", "confidence": 0.9}


class _AlwaysFailPreOutputGate(EnforcementGate):
    @property
    def name(self):
        return "always_fail_pre_output_audit_f2"

    @property
    def insertion_point(self):
        return INSERTION_PRE_OUTPUT

    def evaluate(self, invocation, policy, context):
        return GateResult(
            passed=False,
            failures=[{"code": "BLOCKED", "message": "always blocked", "field": None}],
        )


# ── Finding 5: Non-mapping invocations must emit FAIL artifacts ───────────────


class TestFinding5NonMappingFAILArtifact:
    """enforce_invocation/enforce_pre_call with non-mapping input must attach
    a FAIL audit artifact to the raised InvocationValidationError."""

    def test_enforce_invocation_list_attaches_artifact(self):
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_invocation([])
        artifact = exc_info.value.audit_artifact
        assert artifact is not None, "FAIL artifact must be attached to exception"
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["failure_gate"] == "invocation_validation"

    def test_enforce_invocation_list_emits_sink(self):
        """FAIL artifact from non-mapping path must not cause an unhandled sink error."""
        with pytest.raises(InvocationValidationError):
            enforce_invocation([])

    def test_enforce_pre_call_list_attaches_artifact(self):
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_pre_call([])
        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["failure_gate"] == "invocation_validation"

    def test_enforce_invocation_string_attaches_artifact(self):
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_invocation("not a dict")
        assert exc_info.value.audit_artifact is not None

    def test_enforce_pre_call_none_attaches_artifact(self):
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_pre_call(None)
        assert exc_info.value.audit_artifact is not None

    def test_aigc_enforce_list_attaches_artifact(self):
        engine = AIGC()
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce([])
        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"

    def test_aigc_enforce_pre_call_list_attaches_artifact(self):
        engine = AIGC()
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_pre_call([])
        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"

    @pytest.mark.asyncio
    async def test_enforce_pre_call_async_list_attaches_artifact(self):
        with pytest.raises(InvocationValidationError) as exc_info:
            await enforce_pre_call_async([])
        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"

    @pytest.mark.asyncio
    async def test_aigc_enforce_pre_call_async_list_attaches_artifact(self):
        engine = AIGC()
        with pytest.raises(InvocationValidationError) as exc_info:
            await engine.enforce_pre_call_async([])
        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"
