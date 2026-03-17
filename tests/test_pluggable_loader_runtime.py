"""Tests proving the pluggable PolicyLoader is wired into AIGC runtime enforcement.

These tests verify that AIGC(policy_loader=...) actually uses the custom loader
during enforcement, not the filesystem. They exercise the full enforcement
pipeline end-to-end with non-filesystem policy references.
"""
from __future__ import annotations

import asyncio

import pytest
from typing import Any

from aigc._internal.enforcement import AIGC
from aigc._internal.policy_loader import PolicyLoaderBase, PolicyCache
from aigc._internal.errors import PolicyLoadError, GovernanceViolationError


# ── Custom loader implementations ────────────────────────────────


class InMemoryPolicyLoader(PolicyLoaderBase):
    """Loads policies from an in-memory dict."""

    def __init__(self, policies: dict[str, dict[str, Any]]):
        self._policies = policies
        self.load_count = 0

    def load(self, policy_ref: str) -> dict[str, Any]:
        self.load_count += 1
        if policy_ref not in self._policies:
            raise PolicyLoadError(
                f"Not found: {policy_ref}",
                details={"ref": policy_ref},
            )
        return self._policies[policy_ref]


# ── Shared fixtures ──────────────────────────────────────────────

VALID_POLICY = {
    "policy_version": "1.0",
    "roles": ["planner"],
}

VALID_INVOCATION = {
    "policy_file": "my-policy-id",
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "planner",
    "input": {"prompt": "test"},
    "output": {"result": "ok"},
    "context": {},
}


def _make_invocation(**overrides: Any) -> dict[str, Any]:
    inv = dict(VALID_INVOCATION)
    inv.update(overrides)
    return inv


# ── 1. Custom loader is used instead of filesystem ───────────────


def test_aigc_enforce_uses_custom_loader():
    """AIGC(policy_loader=InMemoryLoader).enforce() actually invokes the
    custom loader and does not hit the filesystem. The policy_file value
    'my-policy-id' has no corresponding file on disk.
    """
    loader = InMemoryPolicyLoader({"my-policy-id": VALID_POLICY})
    aigc = AIGC(policy_loader=loader)

    artifact = aigc.enforce(VALID_INVOCATION)

    assert artifact["enforcement_result"] == "PASS"
    assert loader.load_count >= 1


# ── 2. PASS artifact has correct fields ──────────────────────────


def test_pass_artifact_has_correct_fields():
    """The returned audit artifact on PASS has the standard structure."""
    loader = InMemoryPolicyLoader({"my-policy-id": VALID_POLICY})
    aigc = AIGC(policy_loader=loader)

    artifact = aigc.enforce(VALID_INVOCATION)

    assert artifact["enforcement_result"] == "PASS"
    assert artifact["policy_version"] == "1.0"
    assert artifact["role"] == "planner"
    assert artifact["model_provider"] == "openai"
    assert artifact["model_identifier"] == "gpt-4"
    assert "input_checksum" in artifact
    assert "output_checksum" in artifact
    assert "timestamp" in artifact
    assert artifact["failures"] is None or artifact["failures"] == []
    assert artifact["failure_gate"] is None
    assert artifact["failure_reason"] is None

    # gates_evaluated must be present in metadata
    metadata = artifact.get("metadata", {})
    assert "gates_evaluated" in metadata
    gates = metadata["gates_evaluated"]
    assert len(gates) > 0


# ── 3. Custom loader roles are enforced ──────────────────────────


def test_custom_loader_roles_are_enforced():
    """Roles declared in the custom-loaded policy are used by enforcement.
    A role that IS in the custom policy passes.
    """
    policy_with_roles = {
        "policy_version": "1.0",
        "roles": ["analyst", "reviewer"],
    }
    loader = InMemoryPolicyLoader({"role-check": policy_with_roles})
    aigc = AIGC(policy_loader=loader)

    inv = _make_invocation(policy_file="role-check", role="analyst")
    artifact = aigc.enforce(inv)
    assert artifact["enforcement_result"] == "PASS"
    assert artifact["role"] == "analyst"


# ── 4. Missing role causes governance failure ────────────────────


def test_custom_loader_wrong_role_fails():
    """A custom loader that returns a policy without the declared role
    causes a GovernanceViolationError.
    """
    policy_no_executor = {
        "policy_version": "1.0",
        "roles": ["planner"],
    }
    loader = InMemoryPolicyLoader({"strict-roles": policy_no_executor})
    aigc = AIGC(policy_loader=loader)

    inv = _make_invocation(policy_file="strict-roles", role="executor")

    with pytest.raises(GovernanceViolationError) as exc_info:
        aigc.enforce(inv)

    # The exception must carry an audit artifact (fail-closed)
    assert exc_info.value.audit_artifact is not None
    assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"


# ── 5. Caching works with custom loader ──────────────────────────


def test_custom_loader_caching():
    """PolicyCache caches the custom-loaded policy; the loader's load()
    is called only once for repeated enforcements.
    """
    loader = InMemoryPolicyLoader({"cached-policy": VALID_POLICY})
    aigc = AIGC(policy_loader=loader)

    artifact1 = aigc.enforce(VALID_INVOCATION | {"policy_file": "cached-policy"})
    assert artifact1["enforcement_result"] == "PASS"

    initial_load_count = loader.load_count

    artifact2 = aigc.enforce(VALID_INVOCATION | {"policy_file": "cached-policy"})
    assert artifact2["enforcement_result"] == "PASS"

    # Second call should hit cache — load_count must not increase
    assert loader.load_count == initial_load_count


# ── 6. Filesystem path is NOT required ───────────────────────────


def test_no_filesystem_path_required():
    """With a custom loader, the policy_file can be an arbitrary string
    that does not correspond to any filesystem path. This must not
    raise a PolicyLoadError about missing files.
    """
    arbitrary_refs = [
        "org/team/policy-v3",
        "db://policies/12345",
        "urn:aigc:policy:production:latest",
        "just-a-slug",
    ]

    for ref in arbitrary_refs:
        loader = InMemoryPolicyLoader({ref: VALID_POLICY})
        aigc = AIGC(policy_loader=loader)
        inv = _make_invocation(policy_file=ref)
        artifact = aigc.enforce(inv)
        assert artifact["enforcement_result"] == "PASS", (
            f"Failed for policy_file={ref!r}"
        )


# ── 7. Deterministic behavior ────────────────────────────────────


def test_deterministic_checksums_with_custom_loader():
    """Same invocation + custom-loaded policy produces identical
    checksums across multiple enforcement runs.
    """
    loader = InMemoryPolicyLoader({"det-policy": VALID_POLICY})
    aigc = AIGC(policy_loader=loader)

    inv = _make_invocation(policy_file="det-policy")

    artifact1 = aigc.enforce(inv)
    artifact2 = aigc.enforce(inv)

    assert artifact1["input_checksum"] == artifact2["input_checksum"]
    assert artifact1["output_checksum"] == artifact2["output_checksum"]
    assert artifact1["enforcement_result"] == artifact2["enforcement_result"]


# ── 8. Async enforce works with custom loader ────────────────────


@pytest.mark.asyncio
async def test_async_enforce_uses_custom_loader():
    """AIGC.enforce_async() also uses the custom policy_loader,
    producing a PASS artifact without filesystem access.
    """
    loader = InMemoryPolicyLoader({"async-policy": VALID_POLICY})
    aigc = AIGC(policy_loader=loader)

    inv = _make_invocation(policy_file="async-policy")
    artifact = await aigc.enforce_async(inv)

    assert artifact["enforcement_result"] == "PASS"
    assert artifact["policy_version"] == "1.0"
    assert artifact["role"] == "planner"
    assert loader.load_count >= 1


@pytest.mark.asyncio
async def test_async_enforce_custom_loader_failure():
    """Async enforcement with a custom loader that raises PolicyLoadError
    for a missing policy produces a FAIL artifact.
    """
    loader = InMemoryPolicyLoader({})  # No policies registered
    aigc = AIGC(policy_loader=loader)

    inv = _make_invocation(policy_file="nonexistent")

    with pytest.raises(PolicyLoadError, match="Not found"):
        await aigc.enforce_async(inv)


@pytest.mark.asyncio
async def test_async_and_sync_produce_same_stable_fields():
    """Async and sync enforcement with the same custom loader and
    invocation must produce identical stable audit fields.
    """
    loader = InMemoryPolicyLoader({"parity-policy": VALID_POLICY})
    aigc = AIGC(policy_loader=loader)

    inv = _make_invocation(policy_file="parity-policy")

    sync_artifact = aigc.enforce(inv)
    async_artifact = await aigc.enforce_async(inv)

    stable_fields = [
        "audit_schema_version",
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
        assert async_artifact[field] == sync_artifact[field], (
            f"Mismatch on stable field: {field}"
        )


# ── Edge case: custom loader policy_ref not found ────────────────


def test_custom_loader_not_found_produces_fail_artifact():
    """When the custom loader raises PolicyLoadError, the AIGC class
    still produces a FAIL audit artifact attached to the exception.
    """
    loader = InMemoryPolicyLoader({})
    aigc = AIGC(policy_loader=loader)

    inv = _make_invocation(policy_file="missing-policy")

    with pytest.raises(PolicyLoadError) as exc_info:
        aigc.enforce(inv)

    assert exc_info.value.audit_artifact is not None
    assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"
