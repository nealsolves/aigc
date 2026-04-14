from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_lab9_compare_low_risk():
    r = client.post("/api/lab9/compare", json={"scenario_key": "low_risk_faq"})
    assert r.status_code == 200
    data = r.json()
    assert data["scenario_key"] == "low_risk_faq"
    assert data["artifact"] == data["governed"]["artifact"]
    assert data["governed"]["artifact"]["enforcement_result"] == "PASS"
    assert data["ungoverned"]["artifact"]["enforcement_result"] == "PASS"
    assert data["ungoverned"]["artifact"]["metadata"]["mode"] == "ungoverned"
    assert data["ungoverned"]["artifact"]["metadata"]["gates_evaluated"] == []


def test_lab9_compare_high_risk():
    r = client.post("/api/lab9/compare", json={"scenario_key": "high_risk_drug_interaction"})
    assert r.status_code == 200
    data = r.json()
    governed = data["governed"]
    ungoverned = data["ungoverned"]
    # Strict mode + high-risk scenario: governed FAILS, ungoverned always PASS
    assert governed["artifact"]["enforcement_result"] == "FAIL"
    assert governed["error"] is not None
    assert ungoverned["artifact"]["enforcement_result"] == "PASS"
    assert ungoverned["error"] is None
    # Top-level artifact is the governed artifact for auditHistory ingestion
    assert data["artifact"] == governed["artifact"]


def test_lab9_unknown_scenario():
    r = client.post("/api/lab9/compare", json={"scenario_key": "nonexistent"})
    assert r.status_code == 422
