"""Edge case tests for split enforcement.

Covers misuse scenarios, boundary conditions, and invariants that
the happy-path and golden-replay tests do not exercise.
"""

import json
import pickle

import jsonschema
import pytest
from collections import OrderedDict
from pathlib import Path

from aigc._internal.audit import checksum
from aigc._internal.enforcement import (
    AIGC,
    PreCallResult,
    enforce_post_call,
    enforce_pre_call,
)
from aigc._internal.errors import (
    GovernanceViolationError,
    InvocationValidationError,
    SchemaValidationError,
)


# ── Helpers ────────────────────────────────────────────────────────

GOLDEN_POLICY = "tests/golden_replays/golden_policy_v1.yaml"
AUDIT_SCHEMA_PATH = Path("schemas/audit_artifact.schema.json")


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
    return {"result": "test output", "confidence": 0.95}


# ── EDGE-01: enforce_post_call without prior enforce_pre_call ──────


class TestPostCallWithoutPreCall:

    def test_enforce_post_call_with_string_fails(self):
        """Passing a string to enforce_post_call raises."""
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call("not a PreCallResult", {"output": "data"})

        assert exc_info.value.audit_artifact is not None
        assert exc_info.value.details["received_type"] == "str"

    def test_enforce_post_call_with_dict_fails(self):
        """Passing a plain dict to enforce_post_call raises."""
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call({"fake": "token"}, {"output": "data"})

        assert exc_info.value.audit_artifact is not None
        assert exc_info.value.details["received_type"] == "dict"

    def test_enforce_post_call_with_none_pre_call_result_fails(self):
        """Passing None as pre_call_result raises."""
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(None, {"output": "data"})

        assert exc_info.value.audit_artifact is not None
        assert exc_info.value.details["received_type"] == "NoneType"

    def test_enforce_post_call_with_integer_fails(self):
        """Passing an integer to enforce_post_call raises."""
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(42, {"output": "data"})

        assert exc_info.value.audit_artifact is not None


# ── EDGE-03: Same PreCallResult used twice ─────────────────────────


class TestPreCallResultReuse:

    def test_precall_result_reuse_fails_closed(self):
        """Reusing a PreCallResult raises InvocationValidationError."""
        pre = enforce_pre_call(_pre_call_invocation())
        enforce_post_call(pre, _valid_output())

        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, _valid_output())

        assert "already been consumed" in str(exc_info.value)
        assert exc_info.value.audit_artifact is not None


# ── EDGE-04: Phase A pre-pipeline failure artifact schema validity ─


class TestPhaseAPrePipelineFailArtifact:

    def test_phase_a_pre_pipeline_fail_artifact_is_schema_valid(self):
        """When policy file is missing, artifact is audit-schema-valid."""
        schema = json.loads(AUDIT_SCHEMA_PATH.read_text())

        invocation = {
            "policy_file": "nonexistent_policy_file.yaml",
            "model_provider": "openai",
            "model_identifier": "gpt-4",
            "role": "tester",
            "input": {},
            "context": {},
        }

        with pytest.raises(Exception) as exc_info:
            enforce_pre_call(invocation)

        artifact = exc_info.value.audit_artifact
        jsonschema.validate(artifact, schema)
        assert artifact["metadata"].get("enforcement_mode") == (
            "split_pre_call_only"
        )

    def test_phase_a_mid_pipeline_fail_artifact_is_schema_valid(self):
        """When role validation fails, artifact is audit-schema-valid."""
        schema = json.loads(AUDIT_SCHEMA_PATH.read_text())

        invocation = _pre_call_invocation(role="unauthorized_role")

        with pytest.raises(GovernanceViolationError) as exc_info:
            enforce_pre_call(invocation)

        artifact = exc_info.value.audit_artifact
        jsonschema.validate(artifact, schema)
        assert artifact["enforcement_result"] == "FAIL"


# ── EDGE-05: Phase A fail artifact output checksum ─────────────────


class TestPhaseAFailOutputChecksum:

    def test_phase_a_fail_artifact_output_checksum_is_empty_dict_hash(
        self,
    ):
        """Phase A FAIL artifact uses checksum({}) for output_checksum."""
        expected_checksum = checksum({})

        invocation = _pre_call_invocation(role="unauthorized_role")

        with pytest.raises(GovernanceViolationError) as exc_info:
            enforce_pre_call(invocation)

        artifact = exc_info.value.audit_artifact
        assert artifact["output_checksum"] == expected_checksum


# ── Output validation edge cases ───────────────────────────────────


class TestPostCallOutputValidation:

    def test_enforce_post_call_with_none_output_fails(self):
        """None output raises InvocationValidationError."""
        pre = enforce_pre_call(_pre_call_invocation())

        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, None)

        assert "output must be a dict" in str(exc_info.value)
        assert exc_info.value.audit_artifact is not None

    def test_enforce_post_call_with_list_output_fails(self):
        """List output raises InvocationValidationError."""
        pre = enforce_pre_call(_pre_call_invocation())

        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, [{"result": "test"}])

        assert "output must be a dict" in str(exc_info.value)

    def test_enforce_post_call_with_string_output_fails(self):
        """String output raises InvocationValidationError."""
        pre = enforce_pre_call(_pre_call_invocation())

        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(pre, "just a string")

        assert "output must be a dict" in str(exc_info.value)


# ── Pre-call invocation with Mapping subclass ──────────────────────


class TestPreCallMappingType:

    def test_enforce_pre_call_accepts_ordered_dict(self):
        """enforce_pre_call accepts OrderedDict (Mapping subclass)."""
        inv = OrderedDict(_pre_call_invocation())
        result = enforce_pre_call(inv)
        assert isinstance(result, PreCallResult)


# ── Split artifact gate list separation ────────────────────────────


class TestSplitArtifactGateLists:

    def test_split_pass_has_separate_phase_gate_lists(self):
        """Split PASS artifact has distinct pre/post gate lists."""
        pre = enforce_pre_call(_pre_call_invocation())
        audit = enforce_post_call(pre, _valid_output())

        meta = audit["metadata"]
        pre_gates = meta["pre_call_gates_evaluated"]
        post_gates = meta["post_call_gates_evaluated"]

        # No overlap: pre-call gates are authorization, post-call are output
        assert set(pre_gates).isdisjoint(set(post_gates)), (
            "Pre-call and post-call gate lists must not overlap"
        )

    def test_pre_call_timestamp_leq_post_call_timestamp(self):
        """pre_call_timestamp <= post_call_timestamp in split PASS."""
        pre = enforce_pre_call(_pre_call_invocation())
        audit = enforce_post_call(pre, _valid_output())

        meta = audit["metadata"]
        assert meta["pre_call_timestamp"] <= meta["post_call_timestamp"]

    def test_split_phase_b_fail_has_both_gate_lists(self):
        """Split Phase B FAIL artifact has both pre and post gate lists."""
        pre = enforce_pre_call(_pre_call_invocation())

        # Output missing required 'confidence' field
        with pytest.raises(SchemaValidationError) as exc_info:
            enforce_post_call(pre, {"result": "test"})

        artifact = exc_info.value.audit_artifact
        meta = artifact["metadata"]
        assert "pre_call_gates_evaluated" in meta
        assert "post_call_gates_evaluated" in meta
        assert meta["enforcement_mode"] == "split"


# ── PreCallResult _consumed invariant ──────────────────────────────


class TestConsumedInvariant:

    def test_consumed_is_false_initially(self):
        """_consumed is False immediately after enforce_pre_call."""
        pre = enforce_pre_call(_pre_call_invocation())
        assert pre._consumed is False

    def test_consumed_is_true_after_consume(self):
        """_consumed is True after enforce_post_call."""
        pre = enforce_pre_call(_pre_call_invocation())
        enforce_post_call(pre, _valid_output())
        assert pre._consumed is True

    def test_pickle_consumed_roundtrip_preserves_flag(self):
        """Pickle round-trip after consumption preserves _consumed=True."""
        pre = enforce_pre_call(_pre_call_invocation())
        enforce_post_call(pre, _valid_output())
        assert pre._consumed is True

        roundtripped = pickle.loads(pickle.dumps(pre))
        assert roundtripped._consumed is True

        # Reusing the pickled consumed result should also fail
        with pytest.raises(InvocationValidationError):
            enforce_post_call(roundtripped, _valid_output())


# ── AIGC instance edge cases ───────────────────────────────────────


class TestAIGCInstanceEdgeCases:

    def test_aigc_post_call_with_wrong_type_fails(self):
        """AIGC instance post_call with wrong type raises."""
        aigc = AIGC()

        with pytest.raises(InvocationValidationError) as exc_info:
            aigc.enforce_post_call("not a PreCallResult", {})

        assert exc_info.value.audit_artifact is not None

    def test_aigc_post_call_reuse_consumed_fails(self):
        """AIGC instance rejects reused PreCallResult."""
        aigc = AIGC()
        pre = aigc.enforce_pre_call(_pre_call_invocation())
        aigc.enforce_post_call(pre, _valid_output())

        with pytest.raises(InvocationValidationError) as exc_info:
            aigc.enforce_post_call(pre, _valid_output())

        assert "already been consumed" in str(exc_info.value)
