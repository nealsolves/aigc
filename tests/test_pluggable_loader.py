"""Tests for pluggable PolicyLoader interface (M2 feature)."""
import pytest
from typing import Any

from aigc._internal.policy_loader import (
    PolicyLoaderBase,
    FilePolicyLoader,
    load_policy,
)
from aigc._internal.enforcement import AIGC
from aigc._internal.errors import PolicyLoadError


# ── Custom loader implementations ────────────────────────────────


class InMemoryPolicyLoader(PolicyLoaderBase):
    """Loads policies from an in-memory dict."""

    def __init__(self, policies: dict[str, dict[str, Any]]):
        self._policies = policies

    def load(self, policy_ref: str) -> dict[str, Any]:
        if policy_ref not in self._policies:
            raise PolicyLoadError(
                f"Policy not found in memory: {policy_ref}",
                details={"policy_ref": policy_ref},
            )
        return self._policies[policy_ref]


class BrokenLoader(PolicyLoaderBase):
    """Always raises an unexpected error."""

    def load(self, policy_ref: str) -> dict[str, Any]:
        raise RuntimeError("Database connection failed")


class NonDictLoader(PolicyLoaderBase):
    """Returns a non-dict value."""

    def load(self, policy_ref: str) -> dict[str, Any]:
        return ["not", "a", "dict"]  # type: ignore[return-value]


# ── PolicyLoaderBase interface ───────────────────────────────────


def test_abstract_loader_cannot_instantiate():
    with pytest.raises(TypeError):
        PolicyLoaderBase()


def test_file_loader_is_policy_loader():
    assert isinstance(FilePolicyLoader(), PolicyLoaderBase)


# ── Custom loader with load_policy ───────────────────────────────


def test_custom_loader_success():
    policies = {
        "my-policy": {
            "policy_version": "1.0",
            "roles": ["planner"],
        }
    }
    loader = InMemoryPolicyLoader(policies)
    policy = load_policy("my-policy", loader=loader)
    assert policy["policy_version"] == "1.0"
    assert "planner" in policy["roles"]


def test_custom_loader_not_found():
    loader = InMemoryPolicyLoader({})
    with pytest.raises(PolicyLoadError, match="not found"):
        load_policy("missing", loader=loader)


def test_custom_loader_unexpected_error():
    with pytest.raises(PolicyLoadError, match="Custom policy loader failed"):
        load_policy("anything", loader=BrokenLoader())


def test_custom_loader_non_dict_result():
    with pytest.raises(PolicyLoadError, match="mapping object"):
        load_policy("anything", loader=NonDictLoader())


def test_custom_loader_schema_validation():
    """Custom loaders still go through schema validation."""
    policies = {
        "bad": {"no_policy_version": True}  # Missing required fields
    }
    loader = InMemoryPolicyLoader(policies)
    with pytest.raises(Exception):  # PolicyValidationError
        load_policy("bad", loader=loader)


# ── Default file loader ─────────────────────────────────────────


def test_default_loader_loads_file():
    """Default loader (no custom) loads from filesystem."""
    policy = load_policy("policies/base_policy.yaml")
    assert "policy_version" in policy


def test_file_loader_direct():
    loader = FilePolicyLoader()
    policy = loader.load("policies/base_policy.yaml")
    assert isinstance(policy, dict)
    assert "policy_version" in policy


# ── Integration with AIGC class ──────────────────────────────────


def test_aigc_with_custom_loader():
    """AIGC class accepts a custom policy_loader parameter."""
    # Currently AIGC uses PolicyCache which uses default loader.
    # This test verifies the parameter is accepted.
    aigc = AIGC(policy_loader=InMemoryPolicyLoader({}))
    assert aigc._policy_loader is not None
