"""Golden replay tests for risk scoring (M2)."""
import pytest
from aigc._internal.enforcement import enforce_invocation, AIGC, GATE_RISK
from aigc._internal.errors import RiskThresholdError


RISK_POLICY = "tests/golden_replays/policy_with_risk.yaml"
WARN_POLICY = "tests/golden_replays/policy_with_risk_warn.yaml"


def _invocation(policy_file=RISK_POLICY, role="planner"):
    return {
        "policy_file": policy_file,
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": role,
        "input": {"prompt": "generate report"},
        "output": {"summary": "report content"},
        "context": {"session_id": "golden-risk-1"},
    }


def test_risk_strict_exceeds_threshold():
    """Strict mode fails when risk score exceeds threshold."""
    with pytest.raises(RiskThresholdError) as exc_info:
        enforce_invocation(_invocation())
    audit = exc_info.value.audit_artifact
    assert audit["enforcement_result"] == "FAIL"
    assert audit["failure_gate"] == "risk_scoring"


def test_risk_warn_only_passes():
    """Warn-only mode passes even when risk exceeds threshold."""
    audit = enforce_invocation(_invocation(policy_file=WARN_POLICY))
    assert audit["enforcement_result"] == "PASS"
    assert audit["risk_score"] is not None
    assert audit["risk_score"] > 0


def test_risk_score_recorded_in_artifact():
    """Risk score and basis are recorded in audit metadata."""
    audit = enforce_invocation(_invocation(policy_file=WARN_POLICY))
    assert "risk_scoring" in audit["metadata"]
    scoring = audit["metadata"]["risk_scoring"]
    assert "score" in scoring
    assert "threshold" in scoring
    assert "mode" in scoring
    assert "basis" in scoring
    assert scoring["mode"] == "warn_only"


def test_risk_gate_in_gates_evaluated():
    """Risk scoring gate appears in gates_evaluated."""
    audit = enforce_invocation(_invocation(policy_file=WARN_POLICY))
    assert GATE_RISK in audit["metadata"]["gates_evaluated"]


def test_risk_scoring_deterministic():
    """Same invocation produces identical risk scores."""
    inv = _invocation(policy_file=WARN_POLICY)
    a1 = enforce_invocation(inv)
    a2 = enforce_invocation(inv)
    assert a1["risk_score"] == a2["risk_score"]
    assert a1["metadata"]["risk_scoring"] == a2["metadata"]["risk_scoring"]


def test_risk_via_aigc_class():
    """Risk scoring works through AIGC class with config override."""
    aigc = AIGC(
        risk_config={
            "mode": "warn_only",
            "threshold": 0.1,
            "factors": [
                {"name": "f1", "weight": 0.5, "condition": "no_output_schema"},
            ],
        }
    )
    inv = {
        "policy_file": "policies/base_policy.yaml",
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "input": {},
        "output": {"result": "ok"},
        "context": {"role_declared": True, "schema_exists": True},
    }
    audit = aigc.enforce(inv)
    assert audit["risk_score"] is not None
