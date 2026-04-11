from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_lab10_phase_a_blocks():
    """split_precall_block fails at Phase A — Phase B must be None."""
    r = client.post("/api/lab10/split-trace", json={"scenario_key": "split_precall_block"})
    assert r.status_code == 200
    data = r.json()
    assert data["combined_result"] == "FAIL"
    assert data["phase_a"]["blocked"] is True
    assert data["phase_b"] is None
    assert data["artifact"]["enforcement_result"] == "FAIL"


def test_lab10_both_phases_pass():
    """low_risk_faq passes both Phase A and Phase B."""
    r = client.post("/api/lab10/split-trace", json={"scenario_key": "low_risk_faq"})
    assert r.status_code == 200
    data = r.json()
    assert data["phase_a"]["blocked"] is False
    assert data["phase_b"] is not None
    assert data["artifact"]["enforcement_result"] in ("PASS", "FAIL")
    assert data["artifact"]["metadata"]["enforcement_mode"] == "split"
    # Both phase gate lists must be present
    assert "pre_call_gates_evaluated" in data["artifact"]["metadata"]
    assert "post_call_gates_evaluated" in data["artifact"]["metadata"]


def test_lab10_unknown_scenario():
    r = client.post("/api/lab10/split-trace", json={"scenario_key": "nonexistent"})
    assert r.status_code == 422
