"""
Audit Artifact Contract Test

This test ensures that the audit artifact always contains
required fields in accordance with the AIGC spec.
"""

import json
from pathlib import Path

from jsonschema import validate

from src.audit import generate_audit_artifact

GOLDEN_SUCCESS = "tests/golden_traces/golden_invocation_success.json"
AUDIT_SCHEMA = "schemas/audit_artifact.schema.json"


def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def test_audit_contract():
    """
    Ensure audit artifacts contain all required fields.
    """
    invocation = load_json(GOLDEN_SUCCESS)
    audit = generate_audit_artifact(
        invocation,
        {"policy_version": "1.0"},
        metadata={
            "preconditions_satisfied": ["role_declared", "schema_exists"],
            "postconditions_satisfied": ["output_schema_valid"],
            "schema_validation": "passed",
        },
        timestamp=1700000000,
    )
    schema = load_json(AUDIT_SCHEMA)
    validate(instance=audit, schema=schema)
    assert audit["audit_schema_version"] == "1.0"
    assert audit["enforcement_result"] == "PASS"
    assert audit["policy_file"] == invocation["policy_file"]
    assert audit["failures"] == []


def test_failure_entries_are_canonicalized():
    invocation = load_json(GOLDEN_SUCCESS)
    failures = [
        {"message": "missing output", "code": "INVOCATION_MISSING_FIELD", "field": "output"},
        {"message": "missing role", "code": "INVOCATION_MISSING_FIELD", "field": "role"},
    ]
    audit = generate_audit_artifact(
        invocation,
        {"policy_version": "1.0"},
        enforcement_result="FAIL",
        failures=list(reversed(failures)),
        timestamp=1700000000,
    )
    expected_order = sorted(
        failures,
        key=lambda item: json.dumps(
            {"code": item["code"], "field": item["field"], "message": item["message"]},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ),
    )
    assert audit["failures"] == expected_order


def test_audit_schema_file_exists():
    assert Path(AUDIT_SCHEMA).exists()


def test_audit_includes_guards_evaluated():
    """Verify guards_evaluated in audit metadata when policy has guards."""
    from src.enforcement import enforce_invocation

    # Use guards_multi policy which adds preconditions, not postconditions
    invocation = load_json("tests/golden_traces/golden_invocation_guards_none.json")

    audit = enforce_invocation(invocation)

    assert "guards_evaluated" in audit["metadata"]
    assert isinstance(audit["metadata"]["guards_evaluated"], list)
    assert len(audit["metadata"]["guards_evaluated"]) == 2


def test_audit_includes_tool_constraints():
    """Verify tool_constraints in audit metadata when policy has tools."""
    from src.enforcement import enforce_invocation

    invocation = load_json("tests/golden_traces/golden_invocation_tools_success.json")

    audit = enforce_invocation(invocation)

    assert "tool_constraints" in audit["metadata"]
    assert "tools_checked" in audit["metadata"]["tool_constraints"]
    assert "violations" in audit["metadata"]["tool_constraints"]


def test_audit_includes_conditions_resolved():
    """Verify conditions_resolved in audit metadata when policy has conditions."""
    from src.enforcement import enforce_invocation

    # Use guards_multi policy
    invocation = load_json("tests/golden_traces/golden_invocation_guards_partial.json")

    audit = enforce_invocation(invocation)

    assert "conditions_resolved" in audit["metadata"]
    assert isinstance(audit["metadata"]["conditions_resolved"], dict)
    assert "is_enterprise" in audit["metadata"]["conditions_resolved"]
    assert "audit_enabled" in audit["metadata"]["conditions_resolved"]
