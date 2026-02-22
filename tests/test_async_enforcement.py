"""
Phase 3.1 — Async enforcement tests.

enforce_invocation_async() must produce identical stable results to
enforce_invocation() for the same invocation + policy.
"""

from __future__ import annotations

import pytest

from src.enforcement import enforce_invocation, enforce_invocation_async
from src.errors import (
    GovernanceViolationError,
    InvocationValidationError,
    PreconditionError,
    SchemaValidationError,
)

POLICY = "tests/golden_replays/golden_policy_v1.yaml"

VALID_INVOCATION = {
    "policy_file": POLICY,
    "model_provider": "anthropic",
    "model_identifier": "claude-sonnet-4-5-20250929",
    "role": "planner",
    "input": {"task": "analyse"},
    "output": {"result": "ok", "confidence": 0.9},
    "context": {"role_declared": True, "schema_exists": True},
}


async def test_async_pass_returns_audit_artifact():
    audit = await enforce_invocation_async(VALID_INVOCATION)
    assert audit["enforcement_result"] == "PASS"


async def test_async_stable_fields_match_sync():
    sync_audit = enforce_invocation(VALID_INVOCATION)
    async_audit = await enforce_invocation_async(VALID_INVOCATION)

    stable_fields = [
        "audit_schema_version",
        "policy_file",
        "policy_schema_version",
        "policy_version",
        "model_provider",
        "model_identifier",
        "role",
        "enforcement_result",
        "failures",
        "failure_gate",
        "failure_reason",
        "input_checksum",
        "output_checksum",
    ]
    for field in stable_fields:
        assert async_audit[field] == sync_audit[field], f"Mismatch on field: {field}"


async def test_async_role_violation_raises():
    bad = {**VALID_INVOCATION, "role": "attacker"}
    with pytest.raises(GovernanceViolationError):
        await enforce_invocation_async(bad)


async def test_async_role_violation_emits_fail_audit():
    bad = {**VALID_INVOCATION, "role": "attacker"}
    with pytest.raises(GovernanceViolationError) as exc_info:
        await enforce_invocation_async(bad)
    assert exc_info.value.audit_artifact is not None
    assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"
    assert exc_info.value.audit_artifact["failure_gate"] == "role_validation"


async def test_async_precondition_failure_raises():
    bad = {**VALID_INVOCATION, "context": {"role_declared": False}}
    with pytest.raises(PreconditionError):
        await enforce_invocation_async(bad)


async def test_async_schema_validation_failure_raises():
    bad = {**VALID_INVOCATION, "output": {"result": 123, "confidence": "bad"}}
    with pytest.raises(SchemaValidationError):
        await enforce_invocation_async(bad)


async def test_async_missing_fields_raises():
    with pytest.raises(InvocationValidationError):
        await enforce_invocation_async({})


async def test_async_non_mapping_invocation_raises():
    with pytest.raises(InvocationValidationError):
        await enforce_invocation_async("not-a-dict")


async def test_async_audit_metadata_present():
    audit = await enforce_invocation_async(VALID_INVOCATION)
    assert "preconditions_satisfied" in audit["metadata"]
    assert "postconditions_satisfied" in audit["metadata"]
    assert "schema_validation" in audit["metadata"]
