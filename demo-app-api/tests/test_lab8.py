from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_lab8_sourced_pass():
    r = client.post("/api/lab8/query-kb", json={"scenario_key": "kb_sourced_pass"})
    assert r.status_code == 200
    data = r.json()
    assert data["error"] is None
    assert data["artifact"]["enforcement_result"] == "PASS"
    assert data["source_ids"] == ["clinical-guidelines-2024-p12"]


def test_lab8_unsourced_fail():
    r = client.post("/api/lab8/query-kb", json={"scenario_key": "kb_unsourced_fail"})
    assert r.status_code == 200
    data = r.json()
    assert data["error"] is not None
    assert data["artifact"]["enforcement_result"] == "FAIL"
    assert data["source_ids"] == []


def test_lab8_multi_source_pass():
    r = client.post("/api/lab8/query-kb", json={"scenario_key": "kb_multi_source_pass"})
    assert r.status_code == 200
    data = r.json()
    assert data["error"] is None
    assert data["artifact"]["enforcement_result"] == "PASS"
    assert len(data["source_ids"]) == 3


def test_lab8_unknown_scenario():
    r = client.post("/api/lab8/query-kb", json={"scenario_key": "nonexistent"})
    assert r.status_code == 422
