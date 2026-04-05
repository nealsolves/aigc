"""
AIGC instance-scoped split enforcement tests.

Validates that the AIGC class exposes enforce_pre_call() / enforce_post_call()
instance methods that use the instance policy cache, sink, and configuration
rather than global state.
"""

import pytest

from aigc._internal.enforcement import AIGC, PreCallResult
from aigc._internal.sinks import CallbackAuditSink


# ── Helpers ──────────────────────────────────────────────────────

GOLDEN_POLICY = "tests/golden_replays/golden_policy_v1.yaml"


def _pre_call_invocation(**overrides):
    """Minimal valid pre-call invocation (no output)."""
    inv = {
        "policy_file": GOLDEN_POLICY,
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {"query": "test"},
        "context": {"role_declared": True, "schema_exists": True},
    }
    inv.update(overrides)
    return inv


def _valid_output():
    """Output that satisfies the golden policy schema."""
    return {"result": "test output", "confidence": 0.95}


# ── Tests ────────────────────────────────────────────────────────


def test_aigc_enforce_pre_call_uses_policy_cache():
    """Instance enforce_pre_call() uses instance policy cache on repeat calls."""
    aigc = AIGC()
    inv = _pre_call_invocation()

    # First call — loads and caches the policy
    pre1 = aigc.enforce_pre_call(inv)
    assert isinstance(pre1, PreCallResult)
    assert pre1.policy_file == GOLDEN_POLICY

    # Second call — should succeed using the cached policy
    pre2 = aigc.enforce_pre_call(inv)
    assert isinstance(pre2, PreCallResult)
    assert pre2.policy_file == GOLDEN_POLICY

    # Both should have the same effective policy content
    assert pre1.effective_policy == pre2.effective_policy


def test_aigc_enforce_post_call_does_not_reload_policy():
    """Chain enforce_pre_call + enforce_post_call succeeds without policy reload.

    Phase B must use pre_call_result.effective_policy, not call load_policy().
    """
    aigc = AIGC()
    pre = aigc.enforce_pre_call(_pre_call_invocation())
    audit = aigc.enforce_post_call(pre, _valid_output())

    assert audit["enforcement_result"] == "PASS"
    assert audit["model_provider"] == "openai"
    assert audit["model_identifier"] == "gpt-4"
    assert audit["role"] == "planner"
    assert audit["metadata"]["enforcement_mode"] == "split"


def test_aigc_sink_isolation_in_split_mode():
    """AIGC instance with custom sink receives split-mode artifacts."""
    collected = []
    sink = CallbackAuditSink(callback=collected.append)
    aigc = AIGC(sink=sink)

    pre = aigc.enforce_pre_call(_pre_call_invocation())
    audit = aigc.enforce_post_call(pre, _valid_output())

    # The artifact should have been emitted to our custom sink
    assert len(collected) == 1
    assert collected[0]["enforcement_result"] == "PASS"
    assert collected[0]["metadata"]["enforcement_mode"] == "split"
    # Verify stable fields match the returned artifact
    assert collected[0]["model_provider"] == audit["model_provider"]
    assert collected[0]["model_identifier"] == audit["model_identifier"]
    assert collected[0]["role"] == audit["role"]


def test_aigc_split_artifact_stable_fields():
    """Sync split path produces artifact with expected stable fields."""
    aigc = AIGC()
    pre = aigc.enforce_pre_call(_pre_call_invocation())
    audit = aigc.enforce_post_call(pre, _valid_output())

    # Stable identity fields
    assert audit["model_provider"] == "openai"
    assert audit["model_identifier"] == "gpt-4"
    assert audit["role"] == "planner"
    assert audit["enforcement_result"] == "PASS"

    # Split-mode metadata
    meta = audit["metadata"]
    assert meta["enforcement_mode"] == "split"
    assert "pre_call_gates_evaluated" in meta
    assert "post_call_gates_evaluated" in meta
    assert "pre_call_timestamp" in meta
    assert "post_call_timestamp" in meta

    # policy_version should be present
    assert "policy_version" in audit


@pytest.mark.asyncio
async def test_aigc_enforce_pre_call_async():
    """Async instance pre_call returns PreCallResult with correct fields."""
    aigc = AIGC()
    pre = await aigc.enforce_pre_call_async(_pre_call_invocation())

    assert isinstance(pre, PreCallResult)
    assert pre.policy_file == GOLDEN_POLICY
    assert pre.model_provider == "openai"
    assert pre.model_identifier == "gpt-4"
    assert pre.role == "planner"


@pytest.mark.asyncio
async def test_aigc_enforce_post_call_async():
    """Async instance post_call delegates to sync and returns valid artifact."""
    aigc = AIGC()
    pre = await aigc.enforce_pre_call_async(_pre_call_invocation())
    audit = await aigc.enforce_post_call_async(pre, _valid_output())

    assert audit["enforcement_result"] == "PASS"
    assert audit["metadata"]["enforcement_mode"] == "split"

    # Stable fields match between sync and async
    assert audit["model_provider"] == "openai"
    assert audit["model_identifier"] == "gpt-4"
    assert audit["role"] == "planner"
    assert "policy_version" in audit
