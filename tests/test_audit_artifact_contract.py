"""
Audit Artifact Contract Test

This test ensures that the audit artifact always contains
required fields in accordance with the AIGC spec.
"""

import json
import re
from pathlib import Path

from jsonschema import validate

from aigc._internal.audit import (
    generate_audit_artifact,
    sanitize_failure_message,
    DEFAULT_REDACTION_PATTERNS,
)

GOLDEN_SUCCESS = "tests/golden_replays/golden_invocation_success.json"
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
    assert audit["audit_schema_version"] == "1.1"
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
    from aigc._internal.enforcement import enforce_invocation

    # Use guards_multi policy which adds preconditions, not postconditions
    invocation = load_json("tests/golden_replays/golden_invocation_guards_none.json")

    audit = enforce_invocation(invocation)

    assert "guards_evaluated" in audit["metadata"]
    assert isinstance(audit["metadata"]["guards_evaluated"], list)
    assert len(audit["metadata"]["guards_evaluated"]) == 2


def test_audit_includes_tool_constraints():
    """Verify tool_constraints in audit metadata when policy has tools."""
    from aigc._internal.enforcement import enforce_invocation

    invocation = load_json("tests/golden_replays/golden_invocation_tools_success.json")

    audit = enforce_invocation(invocation)

    assert "tool_constraints" in audit["metadata"]
    assert "tools_checked" in audit["metadata"]["tool_constraints"]
    assert "violations" in audit["metadata"]["tool_constraints"]


def test_audit_includes_conditions_resolved():
    """Verify conditions_resolved in audit metadata when policy has conditions."""
    from aigc._internal.enforcement import enforce_invocation

    # Use guards_multi policy
    invocation = load_json("tests/golden_replays/golden_invocation_guards_partial.json")

    audit = enforce_invocation(invocation)

    assert "conditions_resolved" in audit["metadata"]
    assert isinstance(audit["metadata"]["conditions_resolved"], dict)
    assert "is_enterprise" in audit["metadata"]["conditions_resolved"]
    assert "audit_enabled" in audit["metadata"]["conditions_resolved"]


def test_failures_truncated_at_1000():
    """Verify failures array is bounded at MAX_FAILURES."""
    from aigc._internal.audit import MAX_FAILURES

    invocation = load_json(GOLDEN_SUCCESS)
    failures = [
        {"code": f"ERR_{i}", "message": f"error {i}", "field": None}
        for i in range(1500)
    ]
    audit = generate_audit_artifact(
        invocation,
        {"policy_version": "1.0"},
        enforcement_result="FAIL",
        failures=failures,
        timestamp=1700000000,
    )
    assert len(audit["failures"]) == MAX_FAILURES


def test_metadata_truncated_at_100_keys():
    """Verify metadata is bounded at MAX_METADATA_KEYS."""
    from aigc._internal.audit import MAX_METADATA_KEYS

    invocation = load_json(GOLDEN_SUCCESS)
    metadata = {f"key_{i}": f"val_{i}" for i in range(150)}
    audit = generate_audit_artifact(
        invocation,
        {"policy_version": "1.0"},
        metadata=metadata,
        timestamp=1700000000,
    )
    assert len(audit["metadata"]) == MAX_METADATA_KEYS


def test_context_truncated_at_100_keys():
    """Verify context is bounded at MAX_CONTEXT_KEYS."""
    from aigc._internal.audit import MAX_CONTEXT_KEYS

    invocation = load_json(GOLDEN_SUCCESS)
    invocation["context"] = {f"ctx_{i}": f"val_{i}" for i in range(150)}
    audit = generate_audit_artifact(
        invocation,
        {"policy_version": "1.0"},
        timestamp=1700000000,
    )
    assert len(audit["context"]) == MAX_CONTEXT_KEYS


def test_within_bounds_not_truncated():
    """Verify data within bounds is not truncated."""
    invocation = load_json(GOLDEN_SUCCESS)
    failures = [
        {"code": f"ERR_{i}", "message": f"error {i}", "field": None}
        for i in range(50)
    ]
    audit = generate_audit_artifact(
        invocation,
        {"policy_version": "1.0"},
        enforcement_result="FAIL",
        failures=failures,
        timestamp=1700000000,
    )
    assert len(audit["failures"]) == 50


# --- Sanitization tests ---

def test_sanitize_api_key():
    msg = "Error: invalid key sk-abc1234567890123456"
    sanitized, redacted = sanitize_failure_message(msg)
    assert "sk-abc1234567890123456" not in sanitized
    assert "[REDACTED:api_key]" in sanitized
    assert "api_key" in redacted


def test_sanitize_bearer_token():
    msg = "Authorization failed: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
    sanitized, redacted = sanitize_failure_message(msg)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sanitized
    assert "bearer_token" in redacted


def test_sanitize_email():
    msg = "User user@example.com is not authorized"
    sanitized, redacted = sanitize_failure_message(msg)
    assert "user@example.com" not in sanitized
    assert "email" in redacted


def test_sanitize_ssn():
    msg = "PII detected: 123-45-6789"
    sanitized, redacted = sanitize_failure_message(msg)
    assert "123-45-6789" not in sanitized
    assert "ssn" in redacted


def test_sanitize_no_sensitive_data():
    msg = "Role 'admin' not in allowed roles"
    sanitized, redacted = sanitize_failure_message(msg)
    assert sanitized == msg
    assert redacted == []


def test_sanitize_custom_patterns():
    custom = [("custom_id", re.compile(r"ID-\d{6}"))]
    msg = "Error with ID-123456"
    sanitized, redacted = sanitize_failure_message(msg, patterns=custom)
    assert "ID-123456" not in sanitized
    assert "custom_id" in redacted


def test_sanitize_multiple_patterns():
    msg = "User user@example.com used key sk-abc1234567890123456"
    sanitized, redacted = sanitize_failure_message(msg)
    assert "user@example.com" not in sanitized
    assert "sk-abc1234567890123456" not in sanitized
    assert "email" in redacted
    assert "api_key" in redacted


def test_sanitization_applied_in_enforcement_fail_path():
    """Verify sanitization is applied to failure messages in enforcement."""
    from aigc._internal.enforcement import enforce_invocation
    from aigc._internal.errors import GovernanceViolationError

    invocation = load_json(GOLDEN_SUCCESS)
    invocation["role"] = "attacker"

    try:
        enforce_invocation(invocation)
        assert False, "Should have raised"
    except GovernanceViolationError as exc:
        audit = exc.audit_artifact
        assert "redacted_fields" in audit["metadata"]
        assert isinstance(audit["metadata"]["redacted_fields"], list)
