"""Golden replay tests for split enforcement (Phase A / Phase B).

Validates that split-mode invocations produce audit artifacts whose
stable fields match golden expectations, just as the existing unified
golden replays do.
"""

import json
import pytest
from pathlib import Path

from aigc._internal.enforcement import (
    enforce_invocation,
    enforce_pre_call,
    enforce_post_call,
)
from aigc._internal.errors import (
    GovernanceViolationError,
    InvocationValidationError,
)

GOLDEN_DIR = Path("tests/golden_replays")


def _load(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text())


def _assert_stable_fields(actual: dict, expected: dict) -> None:
    """Assert stable fields match expected, recursively for metadata."""
    for key, expected_val in expected.items():
        assert key in actual, f"Missing key: {key}"
        if isinstance(expected_val, dict):
            # For nested dicts (e.g. metadata), check only keys present
            # in expected (allow extra keys in actual).
            for sub_key, sub_val in expected_val.items():
                assert actual[key].get(sub_key) == sub_val, (
                    f"{key}.{sub_key}: expected {sub_val!r}, "
                    f"got {actual[key].get(sub_key)!r}"
                )
        else:
            assert actual[key] == expected_val, (
                f"{key}: expected {expected_val!r}, got {actual[key]!r}"
            )


def test_golden_split_pass_produces_correct_artifact():
    """Split PASS produces audit artifact with correct stable fields."""
    invocation = _load("golden_invocation_split_pass.json")
    expected = _load("golden_expected_split_pass_audit.json")

    pre_call_result = enforce_pre_call(invocation)
    output = {"result": "architecture overview", "confidence": 0.9}
    artifact = enforce_post_call(pre_call_result, output)

    _assert_stable_fields(artifact, expected)


def test_golden_split_pre_fail_role_produces_correct_artifact():
    """Split Phase A FAIL (role) produces correct stable fields."""
    invocation = _load("golden_invocation_split_pre_fail_role.json")
    expected = _load("golden_expected_split_pre_fail_role_audit.json")

    with pytest.raises(GovernanceViolationError) as exc_info:
        enforce_pre_call(invocation)

    artifact = exc_info.value.audit_artifact
    _assert_stable_fields(artifact, expected)


def test_golden_split_pre_result_is_single_use():
    """PreCallResult can only be consumed once."""
    invocation = _load("golden_invocation_split_pass.json")
    output = {"result": "test", "confidence": 0.9}

    pre_call_result = enforce_pre_call(invocation)
    enforce_post_call(pre_call_result, output)  # first use

    with pytest.raises(InvocationValidationError):
        enforce_post_call(pre_call_result, output)  # second use fails


def test_golden_unified_mode_still_produces_v1_3_artifact():
    """Unified mode still works after split refactor, produces v1.3."""
    invocation = _load("golden_invocation_success.json")
    artifact = enforce_invocation(invocation)

    assert artifact["audit_schema_version"] == "1.3"
    assert artifact["metadata"]["enforcement_mode"] == "unified"
