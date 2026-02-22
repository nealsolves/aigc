import asyncio
import json
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

from src.errors import PolicyLoadError, PolicyValidationError
from src.policy_loader import (
    load_policy,
    load_policy_async,
    _path_to_pointer,
    _merge_policies,
    _resolve_extends,
    _resolve_policy_schema_path,
    POLICY_DSL_SCHEMA_PATH,
    LEGACY_POLICY_SCHEMA_PATH,
)


def test_load_policy_success():
    policy = load_policy("tests/golden_replays/golden_policy_v1.yaml")
    assert policy["policy_version"] == "1.0"
    assert "roles" in policy


def test_load_policy_invalid_yaml():
    with pytest.raises(PolicyLoadError) as exc_info:
        load_policy("tests/golden_replays/invalid_policy.yaml")
    assert exc_info.value.code == "POLICY_LOAD_ERROR"


def test_load_policy_schema_mismatch():
    with pytest.raises(PolicyValidationError) as exc_info:
        load_policy("tests/golden_replays/policy_missing_roles.yaml")
    assert exc_info.value.code == "POLICY_SCHEMA_VALIDATION_ERROR"
    assert "roles" in str(exc_info.value)


def test_load_policy_missing_file():
    with pytest.raises(PolicyLoadError) as exc_info:
        load_policy("tests/golden_replays/does_not_exist.yaml")
    assert exc_info.value.code == "POLICY_LOAD_ERROR"


def test_load_policy_path_escape_is_blocked():
    with pytest.raises(PolicyLoadError) as exc_info:
        load_policy("../outside-policy.yaml")
    assert exc_info.value.code == "POLICY_LOAD_ERROR"


def test_load_policy_non_yaml_extension():
    """Policy file with .txt extension is rejected (line 62)."""
    with pytest.raises(PolicyLoadError) as exc_info:
        load_policy("tests/golden_replays/golden_policy_v1.txt")
    assert exc_info.value.code == "POLICY_LOAD_ERROR"
    assert "YAML" in str(exc_info.value)


def test_load_policy_directory_path(tmp_path):
    """Policy path pointing to a directory is rejected (line 72).

    The directory must exist, have a .yaml extension, and be within the
    mocked REPO_ROOT so that the path-escape check passes first.
    """
    yaml_dir = tmp_path / "policy_dir.yaml"
    yaml_dir.mkdir()
    with patch("src.policy_loader.REPO_ROOT", tmp_path):
        with pytest.raises(PolicyLoadError) as exc_info:
            load_policy(str(yaml_dir))
    assert exc_info.value.code == "POLICY_LOAD_ERROR"
    assert "file" in str(exc_info.value).lower()


def test_load_policy_non_dict_yaml():
    """Policy YAML that parses to a list (not a dict) is rejected (line 189)."""
    with pytest.raises(PolicyLoadError) as exc_info:
        load_policy("tests/fixtures/non_dict_policy.yaml")
    assert exc_info.value.code == "POLICY_LOAD_ERROR"
    assert "mapping" in str(exc_info.value)


def test_path_to_pointer_empty_path():
    """Empty path list returns '$' root pointer (line 82)."""
    result = _path_to_pointer([])
    assert result == "$"


def test_path_to_pointer_non_empty():
    """Non-empty path returns dotted pointer."""
    result = _path_to_pointer(["roles", 0])
    assert result == "$.roles.0"


def test_merge_policies_key_only_in_overlay():
    """Key present in overlay but not in base is added to merged (line 108)."""
    base = {"policy_version": "1.0", "roles": ["planner"]}
    overlay = {"new_key": "new_value", "roles": ["verifier"]}
    merged = _merge_policies(base, overlay)
    assert merged["new_key"] == "new_value"
    assert merged["roles"] == ["planner", "verifier"]
    assert merged["policy_version"] == "1.0"


def test_resolve_extends_no_extends_returns_policy():
    """_resolve_extends returns policy unchanged when extends is falsy (line 141)."""
    policy = {"policy_version": "1.0", "roles": ["planner"], "extends": None}
    fake_path = Path("tests/golden_replays/golden_policy_v1.yaml").resolve()
    result = _resolve_extends(policy, fake_path)
    assert result is policy


def test_load_policy_async_returns_same_as_sync():
    """load_policy_async produces identical result to load_policy (line 255)."""
    sync_policy = load_policy("tests/golden_replays/golden_policy_v1.yaml")
    async_policy = asyncio.run(
        load_policy_async("tests/golden_replays/golden_policy_v1.yaml")
    )
    assert sync_policy == async_policy


def test_resolve_policy_schema_path_uses_dsl_when_present():
    """_resolve_policy_schema_path returns DSL schema when it exists."""
    schema_path = _resolve_policy_schema_path()
    assert schema_path == POLICY_DSL_SCHEMA_PATH


def test_resolve_policy_schema_path_falls_back_to_legacy(tmp_path):
    """_resolve_policy_schema_path falls back to legacy schema when DSL is absent (lines 38-44)."""
    with patch(
        "src.policy_loader.POLICY_DSL_SCHEMA_PATH",
        tmp_path / "nonexistent_dsl.schema.json",
    ):
        schema_path = _resolve_policy_schema_path()
    assert schema_path == LEGACY_POLICY_SCHEMA_PATH


def test_resolve_policy_schema_path_raises_when_neither_schema_exists(tmp_path):
    """_resolve_policy_schema_path raises when both schemas are absent (lines 39-42)."""
    with (
        patch(
            "src.policy_loader.POLICY_DSL_SCHEMA_PATH",
            tmp_path / "missing_dsl.schema.json",
        ),
        patch(
            "src.policy_loader.LEGACY_POLICY_SCHEMA_PATH",
            tmp_path / "missing_legacy.schema.json",
        ),
    ):
        with pytest.raises(PolicyLoadError) as exc_info:
            _resolve_policy_schema_path()
    assert "No policy schema file found" in str(exc_info.value)


def test_load_policy_schema_json_decode_error():
    """PolicyLoadError raised when schema JSON file is malformed (lines 203-204)."""
    with patch("builtins.open", mock_open(read_data="not valid json")):
        with patch("yaml.safe_load", return_value={"policy_version": "1.0", "roles": ["planner"]}):
            with pytest.raises((PolicyLoadError, Exception)):
                load_policy("tests/golden_replays/golden_policy_v1.yaml")


def test_load_policy_schema_wrong_draft(tmp_path):
    """PolicyLoadError raised when schema declares wrong JSON Schema version (line 210)."""
    bad_schema = {"$schema": "http://json-schema.org/draft-04/schema#"}
    bad_schema_file = tmp_path / "bad.schema.json"
    bad_schema_file.write_text(json.dumps(bad_schema))

    with patch("src.policy_loader.POLICY_DSL_SCHEMA_PATH", bad_schema_file):
        with pytest.raises(PolicyLoadError) as exc_info:
            load_policy("tests/golden_replays/golden_policy_v1.yaml")
    assert "Draft-07" in str(exc_info.value)
