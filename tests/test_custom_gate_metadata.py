"""Tests proving custom gate metadata is preserved in audit artifacts.

Verifies that metadata from custom EnforcementGate instances is accumulated
across all insertion points, merged deterministically (sorted keys), and
included in the PASS audit artifact under metadata["custom_gate_metadata"].
"""
import pytest
from typing import Any, Mapping

from aigc._internal.enforcement import AIGC
from aigc._internal.gates import (
    EnforcementGate,
    GateResult,
    INSERTION_PRE_AUTHORIZATION,
    INSERTION_POST_AUTHORIZATION,
    INSERTION_PRE_OUTPUT,
    INSERTION_POST_OUTPUT,
)


VALID_INVOCATION = {
    "policy_file": "tests/golden_replays/golden_policy_v1.yaml",
    "model_provider": "openai",
    "model_identifier": "gpt-4",
    "role": "planner",
    "input": {"prompt": "test"},
    "output": {"result": "ok", "confidence": 0.9},
    "context": {"role_declared": True, "schema_exists": True},
}


# ── Helper gate implementations ──────────────────────────────────


class _MetadataGate(EnforcementGate):
    """Configurable gate that returns arbitrary metadata."""

    def __init__(
        self, gate_name: str, point: str, meta: dict[str, Any],
    ) -> None:
        self._name = gate_name
        self._point = point
        self._meta = meta

    @property
    def name(self) -> str:
        return self._name

    @property
    def insertion_point(self) -> str:
        return self._point

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        return GateResult(passed=True, metadata=self._meta)


class _EmptyMetadataGate(EnforcementGate):
    """Gate that passes with no metadata (empty dict)."""

    def __init__(self, gate_name: str, point: str) -> None:
        self._name = gate_name
        self._point = point

    @property
    def name(self) -> str:
        return self._name

    @property
    def insertion_point(self) -> str:
        return self._point

    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: Mapping[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        return GateResult(passed=True)


# ── Tests ─────────────────────────────────────────────────────────


class TestSingleGateMetadata:
    """A single passing gate's metadata appears in the artifact."""

    def test_metadata_present_in_artifact(self):
        gate = _MetadataGate(
            "tracker", INSERTION_POST_AUTHORIZATION, {"trace_id": "abc-123"},
        )
        aigc = AIGC(custom_gates=[gate])
        artifact = aigc.enforce(VALID_INVOCATION)

        assert artifact["enforcement_result"] == "PASS"
        custom_meta = artifact["metadata"]["custom_gate_metadata"]
        assert custom_meta["trace_id"] == "abc-123"

    def test_metadata_from_pre_auth_gate(self):
        gate = _MetadataGate(
            "pre_auth_tracker",
            INSERTION_PRE_AUTHORIZATION,
            {"origin": "pre_auth"},
        )
        aigc = AIGC(custom_gates=[gate])
        artifact = aigc.enforce(VALID_INVOCATION)

        assert artifact["metadata"]["custom_gate_metadata"]["origin"] == "pre_auth"

    def test_metadata_from_pre_output_gate(self):
        gate = _MetadataGate(
            "pre_out_tracker",
            INSERTION_PRE_OUTPUT,
            {"stage": "pre_output"},
        )
        aigc = AIGC(custom_gates=[gate])
        artifact = aigc.enforce(VALID_INVOCATION)

        assert artifact["metadata"]["custom_gate_metadata"]["stage"] == "pre_output"

    def test_metadata_from_post_output_gate(self):
        gate = _MetadataGate(
            "post_out_tracker",
            INSERTION_POST_OUTPUT,
            {"final": True},
        )
        aigc = AIGC(custom_gates=[gate])
        artifact = aigc.enforce(VALID_INVOCATION)

        assert artifact["metadata"]["custom_gate_metadata"]["final"] is True


class TestMultiGateMetadataMerge:
    """Metadata from multiple gates across different insertion points is merged."""

    def test_two_gates_different_points_merged(self):
        gate_a = _MetadataGate(
            "gate_a", INSERTION_PRE_AUTHORIZATION, {"key_a": "val_a"},
        )
        gate_b = _MetadataGate(
            "gate_b", INSERTION_POST_OUTPUT, {"key_b": "val_b"},
        )
        aigc = AIGC(custom_gates=[gate_a, gate_b])
        artifact = aigc.enforce(VALID_INVOCATION)

        custom_meta = artifact["metadata"]["custom_gate_metadata"]
        assert custom_meta["key_a"] == "val_a"
        assert custom_meta["key_b"] == "val_b"

    def test_four_gates_all_insertion_points_merged(self):
        gates = [
            _MetadataGate("g_pre_auth", INSERTION_PRE_AUTHORIZATION, {"a": 1}),
            _MetadataGate("g_post_auth", INSERTION_POST_AUTHORIZATION, {"b": 2}),
            _MetadataGate("g_pre_out", INSERTION_PRE_OUTPUT, {"c": 3}),
            _MetadataGate("g_post_out", INSERTION_POST_OUTPUT, {"d": 4}),
        ]
        aigc = AIGC(custom_gates=gates)
        artifact = aigc.enforce(VALID_INVOCATION)

        custom_meta = artifact["metadata"]["custom_gate_metadata"]
        assert custom_meta == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_same_point_multiple_gates_metadata_merged(self):
        gate_a = _MetadataGate(
            "tracker_a", INSERTION_POST_AUTHORIZATION, {"x": 10},
        )
        gate_b = _MetadataGate(
            "tracker_b", INSERTION_POST_AUTHORIZATION, {"y": 20},
        )
        aigc = AIGC(custom_gates=[gate_a, gate_b])
        artifact = aigc.enforce(VALID_INVOCATION)

        custom_meta = artifact["metadata"]["custom_gate_metadata"]
        assert custom_meta["x"] == 10
        assert custom_meta["y"] == 20


class TestMetadataKeysSortedDeterministically:
    """Metadata keys are sorted for deterministic artifact generation."""

    def test_keys_are_sorted(self):
        gates = [
            _MetadataGate("z_gate", INSERTION_PRE_AUTHORIZATION, {"zebra": 1}),
            _MetadataGate("a_gate", INSERTION_POST_OUTPUT, {"apple": 2}),
            _MetadataGate("m_gate", INSERTION_POST_AUTHORIZATION, {"mango": 3}),
        ]
        aigc = AIGC(custom_gates=gates)
        artifact = aigc.enforce(VALID_INVOCATION)

        custom_meta = artifact["metadata"]["custom_gate_metadata"]
        keys = list(custom_meta.keys())
        assert keys == sorted(keys), (
            f"Keys must be sorted for determinism, got: {keys}"
        )

    def test_sorted_order_is_alphabetical(self):
        gates = [
            _MetadataGate(
                "multi_meta",
                INSERTION_POST_AUTHORIZATION,
                {"charlie": 3, "alpha": 1, "bravo": 2},
            ),
        ]
        aigc = AIGC(custom_gates=gates)
        artifact = aigc.enforce(VALID_INVOCATION)

        custom_meta = artifact["metadata"]["custom_gate_metadata"]
        assert list(custom_meta.keys()) == ["alpha", "bravo", "charlie"]

    def test_determinism_across_runs(self):
        """Same gates produce identical metadata ordering on repeated runs."""
        gates = [
            _MetadataGate("g1", INSERTION_PRE_AUTHORIZATION, {"z": 1, "a": 2}),
            _MetadataGate("g2", INSERTION_POST_OUTPUT, {"m": 3, "b": 4}),
        ]
        aigc = AIGC(custom_gates=gates)

        artifact_1 = aigc.enforce(VALID_INVOCATION)
        artifact_2 = aigc.enforce(VALID_INVOCATION)

        meta_1 = artifact_1["metadata"]["custom_gate_metadata"]
        meta_2 = artifact_2["metadata"]["custom_gate_metadata"]
        assert list(meta_1.keys()) == list(meta_2.keys())
        assert meta_1 == meta_2


class TestMetadataSurvivesToArtifactOnPass:
    """Gate metadata is present in the final PASS artifact (not lost)."""

    def test_artifact_contains_custom_gate_metadata_key(self):
        gate = _MetadataGate(
            "evidence_gate",
            INSERTION_POST_AUTHORIZATION,
            {"evidence": "preserved"},
        )
        aigc = AIGC(custom_gates=[gate])
        artifact = aigc.enforce(VALID_INVOCATION)

        assert "custom_gate_metadata" in artifact["metadata"]

    def test_complex_metadata_values_preserved(self):
        gate = _MetadataGate(
            "complex_gate",
            INSERTION_POST_AUTHORIZATION,
            {
                "nested": {"level": 2},
                "list_val": [1, 2, 3],
                "bool_val": True,
                "null_val": None,
            },
        )
        aigc = AIGC(custom_gates=[gate])
        artifact = aigc.enforce(VALID_INVOCATION)

        custom_meta = artifact["metadata"]["custom_gate_metadata"]
        assert custom_meta["nested"] == {"level": 2}
        assert custom_meta["list_val"] == [1, 2, 3]
        assert custom_meta["bool_val"] is True
        assert custom_meta["null_val"] is None

    def test_metadata_coexists_with_standard_metadata(self):
        gate = _MetadataGate(
            "coexist_gate",
            INSERTION_POST_AUTHORIZATION,
            {"custom_key": "custom_value"},
        )
        aigc = AIGC(custom_gates=[gate])
        artifact = aigc.enforce(VALID_INVOCATION)

        meta = artifact["metadata"]
        # Standard metadata fields must still be present
        assert "gates_evaluated" in meta
        assert "preconditions_satisfied" in meta
        assert "postconditions_satisfied" in meta
        # Custom metadata also present
        assert meta["custom_gate_metadata"]["custom_key"] == "custom_value"


class TestEmptyMetadataOmitted:
    """Empty metadata from a gate does not create the custom_gate_metadata key."""

    def test_no_metadata_key_when_gate_returns_empty(self):
        gate = _EmptyMetadataGate("no_meta_gate", INSERTION_POST_AUTHORIZATION)
        aigc = AIGC(custom_gates=[gate])
        artifact = aigc.enforce(VALID_INVOCATION)

        assert artifact["enforcement_result"] == "PASS"
        assert "custom_gate_metadata" not in artifact["metadata"]

    def test_no_metadata_key_when_no_custom_gates(self):
        aigc = AIGC()
        artifact = aigc.enforce(VALID_INVOCATION)

        assert artifact["enforcement_result"] == "PASS"
        assert "custom_gate_metadata" not in artifact["metadata"]

    def test_no_metadata_key_when_all_gates_return_empty(self):
        gates = [
            _EmptyMetadataGate("empty_a", INSERTION_PRE_AUTHORIZATION),
            _EmptyMetadataGate("empty_b", INSERTION_POST_OUTPUT),
        ]
        aigc = AIGC(custom_gates=gates)
        artifact = aigc.enforce(VALID_INVOCATION)

        assert "custom_gate_metadata" not in artifact["metadata"]

    def test_metadata_key_present_when_at_least_one_gate_has_data(self):
        gates = [
            _EmptyMetadataGate("empty", INSERTION_PRE_AUTHORIZATION),
            _MetadataGate(
                "has_meta", INSERTION_POST_OUTPUT, {"found": True},
            ),
        ]
        aigc = AIGC(custom_gates=gates)
        artifact = aigc.enforce(VALID_INVOCATION)

        assert "custom_gate_metadata" in artifact["metadata"]
        assert artifact["metadata"]["custom_gate_metadata"]["found"] is True
