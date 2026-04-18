"""Tests for aigc._internal.workflow_doctor."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from aigc._internal.workflow_doctor import (
    diagnose_workflow_policy,
    diagnose_starter_dir,
    diagnose_workflow_artifact,
    diagnose_audit_artifact,
    diagnose_target,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_VALID_POLICY = """\
policy_version: "1.0"
roles:
  - ai-assistant
"""

FUTURE_DATE = "2099-01-01"
PAST_DATE = "2000-01-01"


def _write(tmp_path: Path, filename: str, content: str) -> str:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return str(p)


def _make_starter_dir(tmp_path: Path, profile: str = "minimal") -> Path:
    """
    Create a starter dir that matches the profile (minimal or standard or regulated).
    """
    d = tmp_path / f"starter_{profile}"
    d.mkdir()
    (d / "policy.yaml").write_text(MINIMAL_VALID_POLICY, encoding="utf-8")
    (d / "README.md").write_text("# Starter\n", encoding="utf-8")
    return d


def _make_standard_starter_dir(tmp_path: Path) -> Path:
    d = _make_starter_dir(tmp_path, "standard")
    # Include the approval checkpoint pattern
    workflow_src = """\
import aigc

def _request_human_approval(summary):
    return True

def run(policy_file=None):
    governance = aigc.AIGC()
    with governance.open_session(policy_file=policy_file) as session:
        session.pause()
        approved = _request_human_approval("step 1 result")
        if not approved:
            session.cancel()
            return
        session.resume()
        session.complete()
"""
    (d / "workflow_example.py").write_text(workflow_src, encoding="utf-8")
    return d


def _make_regulated_starter_dir(tmp_path: Path) -> Path:
    d = _make_starter_dir(tmp_path, "regulated")
    workflow_src = """\
import aigc
from aigc import ProvenanceGate

def run(policy_file=None):
    gate = ProvenanceGate(require_source_ids=True)
    governance = aigc.AIGC(custom_gates=[gate])
    with governance.open_session(policy_file=policy_file) as session:
        pre = session.enforce_step_pre_call({
            "context": {"provenance": {"source_ids": ["doc-001"]}},
            "policy_file": policy_file,
            "input": {},
            "output": {},
            "model_provider": "anthropic",
            "model_identifier": "claude-sonnet-4-6",
            "role": "ai-assistant",
        })
        session.enforce_step_post_call(pre, {})
        session.complete()
"""
    (d / "workflow_example.py").write_text(workflow_src, encoding="utf-8")
    return d


def _make_minimal_starter_dir(tmp_path: Path) -> Path:
    d = _make_starter_dir(tmp_path, "minimal_simple")
    workflow_src = """\
import aigc

def run(policy_file=None):
    governance = aigc.AIGC()
    with governance.open_session(policy_file=policy_file) as session:
        session.complete()
"""
    (d / "workflow_example.py").write_text(workflow_src, encoding="utf-8")
    return d


def _make_valid_workflow_artifact(
    status: str = "COMPLETED",
    failure_summary: dict | None = None,
) -> dict:
    steps = 2
    checksums = ["a" * 64 for _ in range(steps)]
    return {
        "workflow_schema_version": "1.0",
        "artifact_type": "workflow",
        "session_id": "sess-001",
        "status": status,
        "started_at": 1700000000,
        "finalized_at": 1700000100,
        "steps": [{"step_id": f"step-{i}"} for i in range(steps)],
        "invocation_audit_checksums": checksums,
        "failure_summary": failure_summary,
        "metadata": {},
    }


def _base_audit_artifact() -> dict:
    """Minimal valid audit artifact shape."""
    return {
        "audit_schema_version": "1.0",
        "policy_file": "policies/base_policy.yaml",
        "policy_schema_version": "1.0",
        "policy_version": "1.0",
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4-6",
        "role": "ai-assistant",
        "enforcement_result": "FAIL",
        "failures": [],
        "failure_gate": None,
        "failure_reason": None,
        "input_checksum": "a" * 64,
        "output_checksum": "b" * 64,
        "timestamp": 1700000000,
        "context": {},
        "metadata": {},
        "risk_score": None,
        "signature": None,
        "provenance": None,
        "chain_id": None,
        "chain_index": None,
        "previous_audit_checksum": None,
        "checksum": None,
    }


def _assert_finding_shape(findings: list[dict]) -> None:
    for f in findings:
        assert "code" in f, f"Missing 'code' in finding: {f}"
        assert "severity" in f, f"Missing 'severity' in finding: {f}"
        assert "message" in f, f"Missing 'message' in finding: {f}"
        assert "next_action" in f, f"Missing 'next_action' in finding: {f}"
        assert f["severity"] in ("ERROR", "WARNING", "INFO"), (
            f"Invalid severity {f['severity']!r}"
        )


# ---------------------------------------------------------------------------
# Policy doctor
# ---------------------------------------------------------------------------

class TestDiagnoseWorkflowPolicy:
    def test_valid_policy_returns_no_findings(self, tmp_path):
        p = _write(tmp_path, "policy.yaml", MINIMAL_VALID_POLICY)
        findings = diagnose_workflow_policy(p, now=date(2025, 6, 1))
        assert findings == []

    def test_expired_policy_returns_error(self, tmp_path):
        content = MINIMAL_VALID_POLICY + f"expiration_date: '{PAST_DATE}'\n"
        p = _write(tmp_path, "expired.yaml", content)
        findings = diagnose_workflow_policy(p, now=date(2025, 6, 1))
        assert any(f["severity"] == "ERROR" for f in findings)
        assert any("expired" in f["message"].lower() for f in findings)

    def test_future_effective_policy_returns_warning(self, tmp_path):
        content = MINIMAL_VALID_POLICY + f"effective_date: '{FUTURE_DATE}'\n"
        p = _write(tmp_path, "future.yaml", content)
        findings = diagnose_workflow_policy(p, now=date(2025, 6, 1))
        assert any(f["severity"] == "WARNING" for f in findings)
        assert any("not yet effective" in f["message"].lower() for f in findings)

    def test_unsupported_binding_warns(self, tmp_path):
        content = (
            MINIMAL_VALID_POLICY
            + "conditions:\n"
            + "  grpc_transport_ready:\n"
            + "    type: boolean\n"
        )
        p = _write(tmp_path, "binding.yaml", content)
        findings = diagnose_workflow_policy(p, now=date(2025, 6, 1))
        codes = [f["code"] for f in findings]
        assert "WORKFLOW_UNSUPPORTED_BINDING" in codes
        matching = [f for f in findings if f["code"] == "WORKFLOW_UNSUPPORTED_BINDING"]
        assert all(f["severity"] == "WARNING" for f in matching)

    def test_no_unsupported_binding_for_normal_conditions(self, tmp_path):
        content = (
            MINIMAL_VALID_POLICY
            + "conditions:\n"
            + "  high_risk:\n"
            + "    type: boolean\n"
        )
        p = _write(tmp_path, "normal.yaml", content)
        findings = diagnose_workflow_policy(p, now=date(2025, 6, 1))
        assert not any(f["code"] == "WORKFLOW_UNSUPPORTED_BINDING" for f in findings)

    def test_token_precondition_emits_info(self, tmp_path):
        content = (
            MINIMAL_VALID_POLICY
            + "pre_conditions:\n"
            + "  required:\n"
            + "    session_token:\n"
            + "      type: string\n"
        )
        p = _write(tmp_path, "token.yaml", content)
        findings = diagnose_workflow_policy(p, now=date(2025, 6, 1))
        codes = [f["code"] for f in findings]
        assert "WORKFLOW_SESSION_TOKEN_INVALID" in codes
        matching = [f for f in findings if f["code"] == "WORKFLOW_SESSION_TOKEN_INVALID"]
        assert all(f["severity"] == "INFO" for f in matching)

    def test_all_findings_have_required_shape(self, tmp_path):
        content = MINIMAL_VALID_POLICY + f"expiration_date: '{PAST_DATE}'\n"
        p = _write(tmp_path, "expired.yaml", content)
        findings = diagnose_workflow_policy(p, now=date(2025, 6, 1))
        _assert_finding_shape(findings)

    def test_defaults_to_today_if_now_not_provided(self, tmp_path):
        p = _write(tmp_path, "policy.yaml", MINIMAL_VALID_POLICY)
        # Should not raise; today is always valid for a policy with no dates
        findings = diagnose_workflow_policy(p)
        assert findings == []


# ---------------------------------------------------------------------------
# Starter directory doctor
# ---------------------------------------------------------------------------

class TestDiagnoseStarterDir:
    def test_standard_starter_emits_approval_advisory(self, tmp_path):
        d = _make_standard_starter_dir(tmp_path)
        findings = diagnose_starter_dir(str(d))
        codes = [f["code"] for f in findings]
        assert "WORKFLOW_APPROVAL_REQUIRED" in codes
        matching = [f for f in findings if f["code"] == "WORKFLOW_APPROVAL_REQUIRED"]
        assert all(f["severity"] == "INFO" for f in matching)

    def test_regulated_starter_emits_source_required_advisory(self, tmp_path):
        d = _make_regulated_starter_dir(tmp_path)
        findings = diagnose_starter_dir(str(d))
        codes = [f["code"] for f in findings]
        assert "WORKFLOW_SOURCE_REQUIRED" in codes
        matching = [f for f in findings if f["code"] == "WORKFLOW_SOURCE_REQUIRED"]
        assert all(f["severity"] == "INFO" for f in matching)

    def test_minimal_starter_without_approval_no_advisory(self, tmp_path):
        d = _make_minimal_starter_dir(tmp_path)
        findings = diagnose_starter_dir(str(d))
        assert not any(f["code"] == "WORKFLOW_APPROVAL_REQUIRED" for f in findings)

    def test_findings_have_next_action(self, tmp_path):
        d = _make_standard_starter_dir(tmp_path)
        findings = diagnose_starter_dir(str(d))
        _assert_finding_shape(findings)

    def test_missing_file_in_starter_returns_error(self, tmp_path):
        d = _make_standard_starter_dir(tmp_path)
        (d / "README.md").unlink()
        findings = diagnose_starter_dir(str(d))
        assert any(f["severity"] == "ERROR" for f in findings)


# ---------------------------------------------------------------------------
# Workflow artifact doctor
# ---------------------------------------------------------------------------

class TestDiagnoseWorkflowArtifact:
    def test_completed_artifact_returns_no_findings(self, tmp_path):
        artifact = _make_valid_workflow_artifact(status="COMPLETED")
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_workflow_artifact(str(p))
        assert findings == []

    def test_failed_with_session_state_error_emits_invalid_transition(self, tmp_path):
        artifact = _make_valid_workflow_artifact(
            status="FAILED",
            failure_summary={
                "exception_type": "SessionStateError",
                "message": "Invalid session lifecycle transition",
            },
        )
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_workflow_artifact(str(p))
        codes = [f["code"] for f in findings]
        assert "WORKFLOW_INVALID_TRANSITION" in codes
        matching = [f for f in findings if f["code"] == "WORKFLOW_INVALID_TRANSITION"]
        assert all(f["severity"] == "ERROR" for f in matching)

    def test_failed_with_lifecycle_message_emits_invalid_transition(self, tmp_path):
        artifact = _make_valid_workflow_artifact(
            status="FAILED",
            failure_summary={
                "exception_type": "RuntimeError",
                "message": "session is not in OPEN state",
            },
        )
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_workflow_artifact(str(p))
        assert any(f["code"] == "WORKFLOW_INVALID_TRANSITION" for f in findings)

    def test_incomplete_artifact_emits_warning(self, tmp_path):
        artifact = _make_valid_workflow_artifact(status="INCOMPLETE")
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_workflow_artifact(str(p))
        assert any(f["code"] == "WORKFLOW_INVALID_TRANSITION" for f in findings)
        assert any(f["severity"] == "WARNING" for f in findings)

    def test_findings_have_required_shape(self, tmp_path):
        artifact = _make_valid_workflow_artifact(
            status="FAILED",
            failure_summary={"exception_type": "SessionStateError", "message": "bad state"},
        )
        p = tmp_path / "wf.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_workflow_artifact(str(p))
        _assert_finding_shape(findings)


# ---------------------------------------------------------------------------
# Audit artifact doctor
# ---------------------------------------------------------------------------

class TestDiagnoseAuditArtifact:
    def test_pass_artifact_returns_no_findings(self, tmp_path):
        artifact = _base_audit_artifact()
        artifact["enforcement_result"] = "PASS"
        artifact["failure_gate"] = None
        artifact["failure_reason"] = None
        p = tmp_path / "pass.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_audit_artifact(str(p))
        assert findings == []

    def test_provenance_failure_emits_source_required(self, tmp_path):
        artifact = _base_audit_artifact()
        artifact["failure_gate"] = "custom_gate_violation"
        artifact["failure_reason"] = "ProvenanceGate: source_ids are required"
        artifact["failures"] = [
            {"code": "PROVENANCE_MISSING", "message": "source IDs required", "field": None}
        ]
        p = tmp_path / "prov.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_audit_artifact(str(p))
        codes = [f["code"] for f in findings]
        assert "WORKFLOW_SOURCE_REQUIRED" in codes
        matching = [f for f in findings if f["code"] == "WORKFLOW_SOURCE_REQUIRED"]
        assert all(f["severity"] == "ERROR" for f in matching)

    def test_tool_validation_failure_emits_tool_budget_exceeded(self, tmp_path):
        artifact = _base_audit_artifact()
        artifact["failure_gate"] = "tool_validation"
        artifact["failure_reason"] = "Tool 'search' exceeded max_calls limit"
        p = tmp_path / "tool.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_audit_artifact(str(p))
        codes = [f["code"] for f in findings]
        assert "WORKFLOW_TOOL_BUDGET_EXCEEDED" in codes
        matching = [f for f in findings if f["code"] == "WORKFLOW_TOOL_BUDGET_EXCEEDED"]
        assert all(f["severity"] == "ERROR" for f in matching)

    def test_session_token_misuse_emits_session_token_invalid(self, tmp_path):
        artifact = _base_audit_artifact()
        artifact["failure_gate"] = "invocation_validation"
        artifact["failure_reason"] = (
            "SessionPreCallResult cannot be completed via enforce_post_call()"
        )
        p = tmp_path / "token.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_audit_artifact(str(p))
        codes = [f["code"] for f in findings]
        assert "WORKFLOW_SESSION_TOKEN_INVALID" in codes
        matching = [f for f in findings if f["code"] == "WORKFLOW_SESSION_TOKEN_INVALID"]
        assert all(f["severity"] == "ERROR" for f in matching)

    def test_token_already_consumed_emits_session_token_invalid(self, tmp_path):
        artifact = _base_audit_artifact()
        artifact["failure_gate"] = "invocation_validation"
        artifact["failure_reason"] = "token already consumed"
        p = tmp_path / "token2.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_audit_artifact(str(p))
        assert any(f["code"] == "WORKFLOW_SESSION_TOKEN_INVALID" for f in findings)

    def test_unknown_fail_emits_generic_fallback(self, tmp_path):
        artifact = _base_audit_artifact()
        artifact["failure_gate"] = "role_validation"
        artifact["failure_reason"] = "Role 'attacker' not in allowed roles"
        p = tmp_path / "unknown.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_audit_artifact(str(p))
        assert findings  # has some finding
        assert not any(f["code"] == "WORKFLOW_SOURCE_REQUIRED" for f in findings)
        assert not any(f["code"] == "WORKFLOW_TOOL_BUDGET_EXCEEDED" for f in findings)
        assert not any(f["code"] == "WORKFLOW_SESSION_TOKEN_INVALID" for f in findings)

    def test_findings_have_required_shape(self, tmp_path):
        artifact = _base_audit_artifact()
        artifact["failure_gate"] = "tool_validation"
        artifact["failure_reason"] = "exceeded budget"
        p = tmp_path / "shape.json"
        p.write_text(json.dumps(artifact))
        findings = diagnose_audit_artifact(str(p))
        _assert_finding_shape(findings)


# ---------------------------------------------------------------------------
# diagnose_target (unified)
# ---------------------------------------------------------------------------

class TestDiagnoseTarget:
    def test_auto_detects_policy_yaml(self, tmp_path):
        p = _write(tmp_path, "policy.yaml", MINIMAL_VALID_POLICY)
        findings = diagnose_target(p, now=date(2025, 6, 1))
        assert findings == []

    def test_auto_detects_starter_dir(self, tmp_path):
        d = _make_standard_starter_dir(tmp_path)
        findings = diagnose_target(str(d))
        assert any(f["code"] == "WORKFLOW_APPROVAL_REQUIRED" for f in findings)

    def test_unknown_target_returns_error_finding(self, tmp_path):
        p = tmp_path / "file.txt"
        p.write_text("hello")
        findings = diagnose_target(str(p))
        assert findings
        assert any(f["severity"] == "ERROR" for f in findings)

    def test_all_findings_have_next_action(self, tmp_path):
        p = _write(
            tmp_path,
            "expired.yaml",
            MINIMAL_VALID_POLICY + f"expiration_date: '{PAST_DATE}'\n",
        )
        findings = diagnose_target(p, now=date(2025, 6, 1))
        _assert_finding_shape(findings)
