import pytest

from src.errors import PolicyLoadError, PolicyValidationError
from src.policy_loader import load_policy


def test_load_policy_success():
    policy = load_policy("tests/golden_traces/golden_policy_v1.yaml")
    assert policy["policy_version"] == "1.0"
    assert "roles" in policy


def test_load_policy_invalid_yaml():
    with pytest.raises(PolicyLoadError) as exc_info:
        load_policy("tests/golden_traces/invalid_policy.yaml")
    assert exc_info.value.code == "POLICY_LOAD_ERROR"


def test_load_policy_schema_mismatch():
    with pytest.raises(PolicyValidationError) as exc_info:
        load_policy("tests/golden_traces/policy_missing_roles.yaml")
    assert exc_info.value.code == "POLICY_SCHEMA_VALIDATION_ERROR"
    assert "roles" in str(exc_info.value)


def test_load_policy_missing_file():
    with pytest.raises(PolicyLoadError) as exc_info:
        load_policy("tests/golden_traces/does_not_exist.yaml")
    assert exc_info.value.code == "POLICY_LOAD_ERROR"


def test_load_policy_path_escape_is_blocked():
    with pytest.raises(PolicyLoadError) as exc_info:
        load_policy("../outside-policy.yaml")
    assert exc_info.value.code == "POLICY_LOAD_ERROR"
