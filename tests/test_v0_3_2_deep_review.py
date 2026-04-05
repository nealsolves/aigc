"""Regression tests for AIGC v0.3.2 deep review findings.

Each test class maps to one finding from
RELEASE_0.3.2_DEEP_REVIEW_2026-04-04.md.

F-01 — PreCallResult provenance check is bypassable (misuse-detection only)
F-02 — Pickle / deepcopy round-trip breaks valid unconsumed tokens
"""
import copy
import pickle

import pytest

from aigc._internal.enforcement import (
    AIGC,
    PreCallResult,
    _ENFORCEMENT_TOKEN,
    enforce_post_call,
    enforce_pre_call,
)
from aigc._internal.errors import InvocationValidationError


# ── Helpers ───────────────────────────────────────────────────────────────────

GOLDEN_POLICY = "tests/golden_replays/golden_policy_v1.yaml"


def _pre_call_inv(**overrides):
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
    return {"result": "test output", "confidence": 0.95}


# ── F-01: Provenance check — misuse-detection scope ───────────────────────────


class TestF01ProvenanceCheck:
    """
    PreCallResult provenance check rejects accidental direct construction.
    Scope: misuse-detection only (see spec Section 10.6).

    A directly-constructed PreCallResult (no object.__setattr__ on _origin)
    must be rejected by both the module-level and AIGC instance post-call paths.
    """

    def test_directly_constructed_token_rejected_module_path(self):
        """enforce_post_call() rejects a PreCallResult built via public init."""
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(
                PreCallResult(
                    effective_policy={},
                    resolved_guards=(),
                    resolved_conditions={},
                    phase_a_metadata={},
                    invocation_snapshot={},
                    policy_file="p.yaml",
                    model_provider="openai",
                    model_identifier="gpt-4",
                    role="planner",
                ),
                _valid_output(),
            )
        assert "not issued by enforce_pre_call" in str(exc_info.value)

    def test_directly_constructed_token_rejected_aigc_path(self):
        """AIGC.enforce_post_call() rejects a directly-constructed token."""
        engine = AIGC()
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_post_call(
                PreCallResult(
                    effective_policy={},
                    resolved_guards=(),
                    resolved_conditions={},
                    phase_a_metadata={},
                    invocation_snapshot={},
                    policy_file="p.yaml",
                    model_provider="openai",
                    model_identifier="gpt-4",
                    role="planner",
                ),
                _valid_output(),
            )
        assert "not issued by enforce_pre_call" in str(exc_info.value)

    def test_enforcement_token_singleton_is_picklable(self):
        """_ENFORCEMENT_TOKEN round-trips through pickle with identity preserved."""
        restored = pickle.loads(pickle.dumps(_ENFORCEMENT_TOKEN))
        assert restored is _ENFORCEMENT_TOKEN

    def test_enforcement_token_singleton_is_deepcopy_stable(self):
        """copy.deepcopy(_ENFORCEMENT_TOKEN) returns the same singleton."""
        assert copy.deepcopy(_ENFORCEMENT_TOKEN) is _ENFORCEMENT_TOKEN


# ── F-02: Pickle / deepcopy round-trip ───────────────────────────────────────


class TestF02PickleRoundTrip:
    """
    A genuine unconsumed PreCallResult must survive pickle and deepcopy
    round-trips and be accepted by enforce_post_call() (spec Section 10.5).

    A consumed token must remain consumed after the same round-trips.
    """

    # ── pickle ────────────────────────────────────────────────────────────────

    def test_unconsumed_token_is_picklable(self):
        """pickle.dumps() on a fresh token must not raise."""
        pre = enforce_pre_call(_pre_call_inv())
        blob = pickle.dumps(pre)
        assert isinstance(blob, bytes)

    def test_unconsumed_token_accepted_after_pickle_module_path(self):
        """A pickled+unpickled unconsumed token is accepted by enforce_post_call."""
        pre = enforce_pre_call(_pre_call_inv())
        pre_restored = pickle.loads(pickle.dumps(pre))
        artifact = enforce_post_call(pre_restored, _valid_output())
        assert artifact.get("enforcement_result") == "PASS"

    def test_unconsumed_token_accepted_after_pickle_aigc_path(self):
        """Same test via AIGC instance enforce_post_call."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        pre_restored = pickle.loads(pickle.dumps(pre))
        artifact = engine.enforce_post_call(pre_restored, _valid_output())
        assert artifact.get("enforcement_result") == "PASS"

    def test_consumed_token_rejected_after_pickle_module_path(self):
        """A consumed token is still rejected after pickle round-trip."""
        pre = enforce_pre_call(_pre_call_inv())
        enforce_post_call(pre, _valid_output())  # consume it
        pre_restored = pickle.loads(pickle.dumps(pre))
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre_restored, _valid_output())
        assert "already been consumed" in str(exc_info.value)

    def test_consumed_token_rejected_after_pickle_aigc_path(self):
        """Same consumed-after-pickle test via AIGC instance."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        engine.enforce_post_call(pre, _valid_output())
        pre_restored = pickle.loads(pickle.dumps(pre))
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_post_call(pre_restored, _valid_output())
        assert "already been consumed" in str(exc_info.value)

    # ── deepcopy ──────────────────────────────────────────────────────────────

    def test_unconsumed_token_accepted_after_deepcopy_module_path(self):
        """copy.deepcopy of an unconsumed token is accepted by enforce_post_call."""
        pre = enforce_pre_call(_pre_call_inv())
        pre_copy = copy.deepcopy(pre)
        artifact = enforce_post_call(pre_copy, _valid_output())
        assert artifact.get("enforcement_result") == "PASS"

    def test_unconsumed_token_accepted_after_deepcopy_aigc_path(self):
        """Same deepcopy test via AIGC instance."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        pre_copy = copy.deepcopy(pre)
        artifact = engine.enforce_post_call(pre_copy, _valid_output())
        assert artifact.get("enforcement_result") == "PASS"

    def test_consumed_token_rejected_after_deepcopy(self):
        """A consumed token deepcopied is still rejected by enforce_post_call."""
        pre = enforce_pre_call(_pre_call_inv())
        enforce_post_call(pre, _valid_output())
        pre_copy = copy.deepcopy(pre)
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre_copy, _valid_output())
        assert "already been consumed" in str(exc_info.value)
