"""
PreCallResult dataclass contract tests.

Validates immutability, consumption semantics, and field invariants
of the PreCallResult handoff token.
"""

import pickle

import pytest

from aigc._internal.enforcement import (
    enforce_post_call,
    enforce_pre_call,
)
from aigc._internal.errors import InvocationValidationError


def _pre_call_invocation():
    """Minimal valid pre-call invocation (no output)."""
    return {
        "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {"query": "test"},
        "context": {"role_declared": True, "schema_exists": True},
    }


def _valid_output():
    return {"result": "test output", "confidence": 0.95}


class TestPreCallResultFrozen:

    def test_frozen_rejects_assignment(self):
        """Frozen dataclass prevents attribute mutation."""
        result = enforce_pre_call(_pre_call_invocation())

        with pytest.raises(AttributeError):
            result.role = "hacker"

    def test_frozen_rejects_effective_policy_assignment(self):
        """Cannot replace effective_policy on a frozen result."""
        result = enforce_pre_call(_pre_call_invocation())

        with pytest.raises(AttributeError):
            result.effective_policy = {}


class TestPreCallResultPickle:

    def test_pickle_roundtrip_unconsumed(self):
        """Pickle preserves _consumed=False."""
        result = enforce_pre_call(_pre_call_invocation())
        assert result._consumed is False

        roundtripped = pickle.loads(pickle.dumps(result))
        assert roundtripped._consumed is False
        assert roundtripped.role == result.role

    def test_pickle_roundtrip_consumed(self):
        """Pickle preserves _consumed=True after use."""
        result = enforce_pre_call(_pre_call_invocation())
        enforce_post_call(result, _valid_output())
        assert result._consumed is True

        roundtripped = pickle.loads(pickle.dumps(result))
        assert roundtripped._consumed is True


class TestInvocationSnapshot:

    def test_invocation_snapshot_exact_fields(self):
        """Snapshot has exactly the 6 required fields (no output)."""
        result = enforce_pre_call(_pre_call_invocation())

        expected_keys = {
            "policy_file",
            "model_provider",
            "model_identifier",
            "role",
            "input",
            "context",
        }
        assert set(result.invocation_snapshot.keys()) == expected_keys

    def test_invocation_snapshot_has_no_output(self):
        """Output is never stored in the snapshot."""
        result = enforce_pre_call(_pre_call_invocation())
        assert "output" not in result.invocation_snapshot


class TestConsumedBit:

    def test_consumed_bit_flips_on_first_use(self):
        """_consumed starts False, becomes True after enforce_post_call."""
        result = enforce_pre_call(_pre_call_invocation())
        assert result._consumed is False

        enforce_post_call(result, _valid_output())
        assert result._consumed is True

    def test_consumed_bit_second_use_fails(self):
        """Second use raises InvocationValidationError."""
        result = enforce_pre_call(_pre_call_invocation())
        enforce_post_call(result, _valid_output())

        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(result, _valid_output())

        assert "already been consumed" in str(exc_info.value)


class TestResolvedGuards:

    def test_resolved_guards_is_tuple(self):
        """resolved_guards is a tuple, not a list."""
        result = enforce_pre_call(_pre_call_invocation())
        assert isinstance(result.resolved_guards, tuple)
