"""Tests for the AIGC Policy CLI."""

import os
import tempfile
from pathlib import Path

import pytest

from aigc._internal.cli import main, _lint_policy, _validate_policy


POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden_replays"


class TestLintPolicy:
    """Unit tests for _lint_policy."""

    def test_valid_policy_returns_no_errors(self):
        errors = _lint_policy(POLICIES_DIR / "base_policy.yaml")
        assert errors == []

    def test_invalid_yaml_returns_parse_error(self):
        errors = _lint_policy(GOLDEN_DIR / "invalid_policy.yaml")
        assert len(errors) == 1
        assert "YAML parse error" in errors[0]

    def test_nonexistent_file_returns_error(self):
        errors = _lint_policy(Path("/nonexistent/policy.yaml"))
        assert len(errors) == 1
        assert "Cannot read file" in errors[0]

    def test_non_dict_yaml_returns_error(self):
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False
        ) as f:
            f.write("- just\n- a\n- list\n")
            f.flush()
            try:
                errors = _lint_policy(Path(f.name))
                assert len(errors) == 1
                assert "mapping" in errors[0]
            finally:
                os.unlink(f.name)

    def test_schema_violation_returns_errors(self):
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False
        ) as f:
            # Missing required policy_version
            f.write("roles:\n  - planner\n")
            f.flush()
            try:
                errors = _lint_policy(Path(f.name))
                assert len(errors) > 0
                assert any("policy_version" in e for e in errors)
            finally:
                os.unlink(f.name)


class TestValidatePolicy:
    """Unit tests for _validate_policy."""

    def test_valid_policy_returns_no_errors(self):
        errors = _validate_policy(POLICIES_DIR / "base_policy.yaml")
        assert errors == []

    def test_missing_extends_base_returns_error(self):
        errors = _validate_policy(
            GOLDEN_DIR / "policy_extends_nonexistent.yaml"
        )
        assert len(errors) > 0


class TestCLIMain:
    """Integration tests for the CLI entry point."""

    def test_lint_valid_policy_exits_0(self):
        exit_code = main(["policy", "lint", str(POLICIES_DIR / "base_policy.yaml")])
        assert exit_code == 0

    def test_lint_invalid_policy_exits_1(self):
        exit_code = main(["policy", "lint", str(GOLDEN_DIR / "invalid_policy.yaml")])
        assert exit_code == 1

    def test_lint_nonexistent_file_exits_1(self):
        exit_code = main(["policy", "lint", "/nonexistent/policy.yaml"])
        assert exit_code == 1

    def test_validate_valid_policy_exits_0(self):
        exit_code = main(["policy", "validate", str(POLICIES_DIR / "base_policy.yaml")])
        assert exit_code == 0

    def test_validate_invalid_policy_exits_1(self):
        exit_code = main(["policy", "validate", str(GOLDEN_DIR / "invalid_policy.yaml")])
        assert exit_code == 1

    def test_no_command_exits_1(self):
        exit_code = main([])
        assert exit_code == 1

    def test_multiple_files(self):
        exit_code = main([
            "policy", "lint",
            str(POLICIES_DIR / "base_policy.yaml"),
            str(GOLDEN_DIR / "invalid_policy.yaml"),
        ])
        assert exit_code == 1  # one invalid = overall fail

    def test_cli_importable_from_public_api(self):
        from aigc.cli import main as public_main
        assert callable(public_main)
