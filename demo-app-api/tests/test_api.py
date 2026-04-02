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


def test_enforce_medium_risk():
    r = client.post("/api/enforce", json={
        "scenario_key": "medium_risk_medical",
        "mode": "risk_scored",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["artifact"]["enforcement_result"] in ("PASS", "FAIL")
    assert data["artifact"]["model_provider"] == "mock"


def test_enforce_low_risk():
    r = client.post("/api/enforce", json={
        "scenario_key": "low_risk_faq",
        "mode": "strict",
    })
    assert r.status_code == 200
    assert r.json()["artifact"]["enforcement_result"] == "PASS"


def test_enforce_unknown_scenario_key():
    r = client.post("/api/enforce", json={"scenario_key": "nonexistent_key"})
    assert r.status_code == 422


def test_generate_key():
    r = client.post("/api/sign/generate-key")
    assert r.status_code == 200
    key = r.json()["key"]
    assert len(key) == 64  # 32 bytes hex


def test_sign_and_verify():
    # Generate a key
    key = client.post("/api/sign/generate-key").json()["key"]

    # Sign via enforcement
    r = client.post("/api/sign/enforce", json={"scenario_key": "signing_basic", "key": key})
    assert r.status_code == 200
    artifact = r.json()["artifact"]
    assert "signature" in artifact

    # Verify — should be valid
    r2 = client.post("/api/sign/verify", json={"artifact": artifact, "key": key})
    assert r2.json()["valid"] is True

    # Tamper and re-verify — should be invalid
    artifact["enforcement_result"] = "FAIL" if artifact["enforcement_result"] == "PASS" else "PASS"
    r3 = client.post("/api/sign/verify", json={"artifact": artifact, "key": key})
    assert r3.json()["valid"] is False


def test_sign_enforce_unknown_scenario_key():
    r = client.post("/api/sign/enforce", json={"scenario_key": "nonexistent", "key": "a" * 64})
    assert r.status_code == 422


def test_sign_verify_bad_hex_key():
    r = client.post("/api/sign/verify", json={"artifact": {}, "key": "not-hex"})
    assert r.status_code == 422


def test_chain_append_first_entry():
    r = client.post("/api/chain/append", json={
        "scenario_key": "chain_entry_1",
        "chain_id": None,
        "previous_checksum": None,
        "chain_index": 0,
    })
    assert r.status_code == 200
    data = r.json()
    artifact = data["artifact"]
    assert artifact["chain_index"] == 0
    assert artifact["previous_audit_checksum"] is None
    assert "checksum" in artifact
    assert "chain_id" in artifact


def test_chain_append_links_correctly():
    # First entry
    r1 = client.post("/api/chain/append", json={
        "scenario_key": "chain_entry_1",
        "chain_id": "test-chain-001",
        "previous_checksum": None,
        "chain_index": 0,
    })
    first = r1.json()["artifact"]

    # Second entry linked to first
    r2 = client.post("/api/chain/append", json={
        "scenario_key": "chain_entry_2",
        "chain_id": "test-chain-001",
        "previous_checksum": first["checksum"],
        "chain_index": 1,
    })
    second = r2.json()["artifact"]
    assert second["previous_audit_checksum"] == first["checksum"]
    assert second["chain_index"] == 1


def test_chain_verify_intact():
    # Build a two-entry chain
    r1 = client.post("/api/chain/append", json={
        "scenario_key": "chain_entry_1",
        "chain_id": "verify-chain-001",
        "previous_checksum": None,
        "chain_index": 0,
    })
    a1 = r1.json()["artifact"]

    r2 = client.post("/api/chain/append", json={
        "scenario_key": "chain_entry_2",
        "chain_id": "verify-chain-001",
        "previous_checksum": a1["checksum"],
        "chain_index": 1,
    })
    a2 = r2.json()["artifact"]

    r3 = client.post("/api/chain/verify", json={"artifacts": [a1, a2]})
    assert r3.json()["valid"] is True
    assert r3.json()["errors"] == []


def test_chain_tamper_breaks_verify():
    r1 = client.post("/api/chain/append", json={
        "scenario_key": "chain_entry_1",
        "chain_id": "tamper-chain-001",
        "previous_checksum": None,
        "chain_index": 0,
    })
    a1 = r1.json()["artifact"]
    r2 = client.post("/api/chain/append", json={
        "scenario_key": "chain_entry_2",
        "chain_id": "tamper-chain-001",
        "previous_checksum": a1["checksum"],
        "chain_index": 1,
    })
    a2 = r2.json()["artifact"]

    # Tamper index 0
    r_tamper = client.post("/api/chain/tamper", json={"artifacts": [a1, a2], "index": 0})
    tampered = r_tamper.json()["artifacts"]

    r_verify = client.post("/api/chain/verify", json={"artifacts": tampered})
    assert r_verify.json()["valid"] is False
    assert len(r_verify.json()["errors"]) > 0
