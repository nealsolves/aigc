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
    assert len(keys) == 11
    assert set(keys) == {
        "low_risk_faq", "medium_risk_medical", "high_risk_drug_interaction",
        "signing_basic", "chain_entry_1", "chain_entry_2", "chain_entry_3",
        "gate_high_confidence", "gate_low_confidence", "gate_pii_present",
        "gate_clean_output",
    }


def test_list_policies():
    r = client.get("/api/policies")
    assert r.status_code == 200
    names = r.json()["policies"]
    assert "medical_ai.yaml" in names
