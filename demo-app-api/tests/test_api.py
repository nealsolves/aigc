from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_scenarios():
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    keys = r.json()["scenarios"]
    assert "medium_risk_medical" in keys
    assert "chain_entry_1" in keys
    assert "gate_pii_present" in keys


def test_list_policies():
    r = client.get("/api/policies")
    assert r.status_code == 200
    names = r.json()["policies"]
    assert "medical_ai.yaml" in names
