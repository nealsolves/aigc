"""
Policy CLI for AIGC governance SDK.

Provides:
- ``aigc policy lint`` — YAML syntax and schema validation
- ``aigc policy validate`` — full semantic validation including extends
- ``aigc compliance export`` — compliance export of audit artifacts
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml
from jsonschema import Draft7Validator, validate, ValidationError

from aigc._internal.policy_loader import (
    _resolve_policy_schema_path,
    load_policy,
)
from aigc._internal.errors import PolicyLoadError, PolicyValidationError
from aigc._internal.lineage import AuditLineage


def _load_schema() -> dict:
    """Load the policy DSL JSON Schema."""
    schema_path = _resolve_policy_schema_path()
    return json.loads(schema_path.read_text())


def _load_audit_schema() -> dict:
    """Load the audit artifact JSON Schema."""
    from aigc._internal.policy_loader import SCHEMAS_DIR
    audit_path = SCHEMAS_DIR / "audit_artifact.schema.json"
    return json.loads(audit_path.read_text())


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
    for err in sorted(
        validator.iter_errors(policy), key=lambda e: list(e.path)
    ):
        pointer = ".".join(str(p) for p in err.absolute_path) or "$"
        errors.append(f"  {pointer}: {err.message}")

    return errors


def _validate_policy(path: Path) -> list[str]:
    """
    Validate a policy file with full semantic checks (load + extends).

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


def _cmd_compliance_export(args: argparse.Namespace) -> int:
    """Run the compliance export subcommand.

    Reads audit artifacts from a JSONL file and produces a compliance
    report in JSON format.
    """
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: file not found: {input_path}", file=sys.stderr)
        return 1

    audit_schema = _load_audit_schema()

    artifacts: list[dict[str, Any]] = []
    invalid_count = 0
    line_num = 0

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line_num += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    artifact = json.loads(line)
                except json.JSONDecodeError:
                    invalid_count += 1
                    continue

                if not isinstance(artifact, dict):
                    invalid_count += 1
                    continue

                # Schema validation of each artifact
                try:
                    validate(instance=artifact, schema=audit_schema)
                    artifacts.append(artifact)
                except ValidationError:
                    invalid_count += 1
    except OSError as e:
        print(f"ERROR: cannot read file: {e}", file=sys.stderr)
        return 1

    # Build compliance report
    pass_count = sum(
        1 for a in artifacts if a.get("enforcement_result") == "PASS"
    )
    fail_count = sum(
        1 for a in artifacts if a.get("enforcement_result") == "FAIL"
    )

    # Collect unique policies
    policies_seen: dict[str, dict[str, Any]] = {}
    for a in artifacts:
        pf = a.get("policy_file", "unknown")
        if pf not in policies_seen:
            policies_seen[pf] = {
                "policy_file": pf,
                "policy_version": a.get("policy_version"),
                "pass_count": 0,
                "fail_count": 0,
                "failure_gates": [],
            }
        if a.get("enforcement_result") == "PASS":
            policies_seen[pf]["pass_count"] += 1
        else:
            policies_seen[pf]["fail_count"] += 1
            fg = a.get("failure_gate")
            if fg and fg not in policies_seen[pf]["failure_gates"]:
                policies_seen[pf]["failure_gates"].append(fg)

    # Collect failure summary
    failure_gates: dict[str, int] = {}
    for a in artifacts:
        if a.get("enforcement_result") == "FAIL":
            fg = a.get("failure_gate", "unknown")
            failure_gates[fg] = failure_gates.get(fg, 0) + 1

    report: dict[str, Any] = {
        "compliance_report_version": "1.0",
        "source_file": str(input_path),
        "total_artifacts": len(artifacts),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "invalid_artifacts": invalid_count,
        "compliance_rate": (
            round(pass_count / len(artifacts) * 100, 2)
            if artifacts else 0.0
        ),
        "failure_gates_summary": dict(
            sorted(failure_gates.items(), key=lambda x: -x[1])
        ),
        "policies": sorted(
            policies_seen.values(), key=lambda p: p["policy_file"]
        ),
    }

    # Include individual artifacts if requested
    if args.include_artifacts:
        report["artifacts"] = artifacts

    # Include lineage analysis if requested
    if args.lineage:
        lin = AuditLineage()
        for a in artifacts:
            lin.add_artifact(a)
        root_keys = [lin.checksum_of(a) for a in lin.roots()]
        leaf_keys = [lin.checksum_of(a) for a in lin.leaves()]
        orphan_keys = [lin.checksum_of(a) for a in lin.orphans()]
        report["lineage"] = {
            "total_nodes": len(lin),
            "duplicate_artifacts": len(artifacts) - len(lin),
            "root_count": len(root_keys),
            "leaf_count": len(leaf_keys),
            "orphan_count": len(orphan_keys),
            "has_cycle": lin.has_cycle(),
            "roots": root_keys,
            "leaves": leaf_keys,
            "orphans": orphan_keys,
        }

    if invalid_count > 0 and len(artifacts) == 0:
        print(
            f"ERROR: all {invalid_count} artifact(s) were schema-invalid; "
            f"nothing exported.",
            file=sys.stderr,
        )
        return 1

    output = json.dumps(report, indent=2, sort_keys=True)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output + "\n", encoding="utf-8")
        print(f"Compliance report written to: {output_path}")
    else:
        print(output)

    return 0


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
        help=(
            "Validate policy files "
            "(lint + semantic checks including extends)"
        ),
    )
    validate_parser.add_argument(
        "files",
        nargs="+",
        help="Policy YAML files to validate",
    )
    validate_parser.set_defaults(func=_cmd_validate)

    # aigc compliance ...
    compliance_parser = subparsers.add_parser(
        "compliance",
        help="Compliance reporting commands",
    )
    compliance_sub = compliance_parser.add_subparsers(dest="subcommand")

    # aigc compliance export --input <file> [--output <file>]
    export_parser = compliance_sub.add_parser(
        "export",
        help="Export compliance report from audit artifact JSONL",
    )
    export_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input JSONL file containing audit artifacts",
    )
    export_parser.add_argument(
        "--output", "-o",
        required=False,
        help="Output file for compliance report (default: stdout)",
    )
    export_parser.add_argument(
        "--include-artifacts",
        action="store_true",
        default=False,
        help="Include individual artifacts in the report",
    )
    export_parser.add_argument(
        "--lineage",
        action="store_true",
        default=False,
        help="Include lineage graph analysis in the compliance report",
    )
    export_parser.set_defaults(func=_cmd_compliance_export)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)
