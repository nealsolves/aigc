"""
Policy CLI for AIGC governance SDK.

Provides ``aigc policy lint`` and ``aigc policy validate`` commands
for offline policy checking.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import yaml
from jsonschema import Draft7Validator, ValidationError

from aigc._internal.policy_loader import (
    _resolve_policy_schema_path,
    load_policy,
)
from aigc._internal.errors import PolicyLoadError, PolicyValidationError


def _load_schema() -> dict:
    """Load the policy DSL JSON Schema."""
    schema_path = _resolve_policy_schema_path()
    return json.loads(schema_path.read_text())


def _lint_policy(path: Path) -> list[str]:
    """
    Lint a single policy file for syntax and schema errors.

    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    # 1. YAML parse
    try:
        raw = path.read_text()
    except OSError as e:
        return [f"Cannot read file: {e}"]

    try:
        policy = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]

    if not isinstance(policy, dict):
        return ["Policy must be a YAML mapping (dict)"]

    # 2. JSON Schema validation
    schema = _load_schema()
    validator = Draft7Validator(schema)
    for err in sorted(validator.iter_errors(policy), key=lambda e: list(e.path)):
        pointer = ".".join(str(p) for p in err.absolute_path) or "$"
        errors.append(f"  {pointer}: {err.message}")

    return errors


def _validate_policy(path: Path) -> list[str]:
    """
    Validate a policy file with full semantic checks (load + extends resolution).

    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    try:
        load_policy(str(path))
    except (PolicyLoadError, PolicyValidationError) as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"Unexpected error: {e}")

    return errors


def _cmd_lint(args: argparse.Namespace) -> int:
    """Run the lint subcommand."""
    exit_code = 0
    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"FAIL  {filepath}: file not found", file=sys.stderr)
            exit_code = 1
            continue

        errors = _lint_policy(path)
        if errors:
            print(f"FAIL  {filepath}")
            for err in errors:
                print(f"  {err}", file=sys.stderr)
            exit_code = 1
        else:
            print(f"OK    {filepath}")

    return exit_code


def _cmd_validate(args: argparse.Namespace) -> int:
    """Run the validate subcommand."""
    exit_code = 0
    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"FAIL  {filepath}: file not found", file=sys.stderr)
            exit_code = 1
            continue

        # Lint first (syntax + schema)
        lint_errors = _lint_policy(path)
        if lint_errors:
            print(f"FAIL  {filepath} (lint)")
            for err in lint_errors:
                print(f"  {err}", file=sys.stderr)
            exit_code = 1
            continue

        # Then full semantic validation
        validate_errors = _validate_policy(path)
        if validate_errors:
            print(f"FAIL  {filepath} (validate)")
            for err in validate_errors:
                print(f"  {err}", file=sys.stderr)
            exit_code = 1
        else:
            print(f"OK    {filepath}")

    return exit_code


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="aigc",
        description="AIGC Governance SDK CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    # aigc policy ...
    policy_parser = subparsers.add_parser(
        "policy",
        help="Policy management commands",
    )
    policy_sub = policy_parser.add_subparsers(dest="subcommand")

    # aigc policy lint <files...>
    lint_parser = policy_sub.add_parser(
        "lint",
        help="Check policy files for YAML syntax and schema errors",
    )
    lint_parser.add_argument(
        "files",
        nargs="+",
        help="Policy YAML files to lint",
    )
    lint_parser.set_defaults(func=_cmd_lint)

    # aigc policy validate <files...>
    validate_parser = policy_sub.add_parser(
        "validate",
        help="Validate policy files (lint + semantic checks including extends)",
    )
    validate_parser.add_argument(
        "files",
        nargs="+",
        help="Policy YAML files to validate",
    )
    validate_parser.set_defaults(func=_cmd_validate)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)
