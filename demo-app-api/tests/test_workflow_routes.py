"""Smoke tests for the v0.9.0 workflow governance demo routes."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Tests rely on conftest.py in demo-app-api/ to add API dir to sys.path.
# Import app from main (same pattern as existing demo tests).
from main import app

client = TestClient(app)


def test_workflow_run_minimal():
    r = client.post("/api/workflow/v090/run", json={"scenario": "minimal"})
    assert r.status_code == 200
    data = r.json()
    assert data["artifact"]["status"] == "COMPLETED"
    assert len(data["artifact"]["steps"]) == 2
    assert "workflow_schema_version" in data["artifact"]
    assert data["error"] is None


def test_workflow_run_standard():
    r = client.post("/api/workflow/v090/run", json={"scenario": "standard"})
    assert r.status_code == 200
    data = r.json()
    assert data["artifact"]["status"] == "COMPLETED"
    assert len(data["artifact"]["steps"]) == 3
    assert data["error"] is None


def test_workflow_run_failure():
    r = client.post("/api/workflow/v090/run", json={"scenario": "failure"})
    assert r.status_code == 200
    data = r.json()
    assert data["artifact"]["status"] == "FAILED"
    assert data["artifact"]["failure_summary"] is not None
    assert data["error"] is not None
    assert "run_id" in data and data["run_id"], "failure response must include a non-empty run_id"


def test_workflow_failure_starter_dir_uses_managed_tempdir():
    import workflow_routes

    r = client.post("/api/workflow/v090/run", json={"scenario": "failure"})
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    starter_dir = workflow_routes._run_state[run_id]["starter_dir"]
    assert Path(starter_dir).is_dir()
    assert Path(starter_dir).parent == Path(workflow_routes._POLICY_TMPDIR.name)


def test_workflow_compare():
    r = client.post("/api/workflow/v090/compare")
    assert r.status_code == 200
    data = r.json()
    assert data["governed"]["artifact"]["status"] == "COMPLETED"
    assert "ungoverned" in data
    assert data["ungoverned"]["artifact"]["audit_available"] is False


def test_workflow_diagnose_no_prior_failure():
    # Use a fresh client with a cleared run_state to avoid state from other tests
    import workflow_routes
    original_state = dict(workflow_routes._run_state)
    workflow_routes._run_state.clear()
    try:
        fresh_client = TestClient(app)
        r = fresh_client.get("/api/workflow/v090/diagnose")
        assert r.status_code == 200
        data = r.json()
        assert "findings" in data
        assert isinstance(data["findings"], list)
        assert data["source"] == "no_prior_failure"
    finally:
        workflow_routes._run_state.update(original_state)


def test_workflow_diagnose_after_failure():
    # Trigger a failure and use the returned run_id to diagnose that specific run.
    fail_r = client.post("/api/workflow/v090/run", json={"scenario": "failure"})
    assert fail_r.status_code == 200
    run_id = fail_r.json()["run_id"]
    assert run_id, "failure response must include a run_id"

    r = client.get(f"/api/workflow/v090/diagnose?run_id={run_id}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["findings"], list)
    codes = [f["code"] for f in data["findings"]]
    assert "WORKFLOW_SOURCE_REQUIRED" in codes, (
        f"Expected WORKFLOW_SOURCE_REQUIRED in findings. Got: {codes}"
    )


def test_policy_cache_uses_managed_tempdir():
    import workflow_routes
    workflow_routes._policy_cache.clear()

    path1 = workflow_routes._get_policy_path("minimal")
    path2 = workflow_routes._get_policy_path("minimal")

    assert path1 == path2
    assert Path(path1).is_file()
    assert Path(path1).parent == Path(workflow_routes._POLICY_TMPDIR.name)


def test_workflow_run_regulated():
    # The "fix applied" regulated scenario — includes provenance.source_ids
    r = client.post("/api/workflow/v090/run", json={"scenario": "regulated"})
    assert r.status_code == 200
    data = r.json()
    assert data["artifact"]["status"] == "COMPLETED"
    assert data["error"] is None
