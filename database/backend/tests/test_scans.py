"""Phase 5C: Scan API tests."""

import time
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app

_counter = 0

def _unique_email():
    global _counter
    _counter += 1
    return f"scanuser{_counter}_{int(time.time())}@test.com"

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def _register_and_login(client):
    email = _unique_email()
    client.post("/api/v1/auth/register", json={
        "name": "Scan Tester",
        "company": f"Scan Corp {_counter}",
        "email": email,
        "password": "StrongPass1!"
    })
    resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "StrongPass1!"
    })
    return resp.json()["access_token"]

def _create_project(client, token):
    resp = client.post("/api/v1/projects", json={
        "name": f"scan-repo-{int(time.time())}",
        "description": "Test repository",
        "language": "TypeScript",
        "visibility": "PRIVATE",
        "branch": "main"
    }, headers={"Authorization": f"Bearer {token}"})
    return resp.json()

def _create_artifact(client, token, project_id):
    manifest = b'{"name": "test-package", "version": "1.0.0", "dependencies": {"express": "^4.17.1"}}'
    files = {"file": ("package.json", manifest, "application/json")}
    resp = client.post(
        f"/api/v1/projects/{project_id}/artifacts",
        headers={"Authorization": f"Bearer {token}"},
        files=files
    )
    return resp.json()

def test_scan_lifecycle(client):
    """Test creating a scan, and polling its status until completed."""
    token = _register_and_login(client)
    project = _create_project(client, token)
    artifact = _create_artifact(client, token, project["id"])
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create Scan
    payload = {
        "artifact_id": artifact["id"],
        "scan_type": "FULL",
        "configuration": {"foo": "bar"}
    }
    resp = client.post(
        f"/api/v1/projects/{project['id']}/scans",
        headers=headers,
        json=payload
    )
    assert resp.status_code == 201
    scan = resp.json()
    assert scan["status"] == "QUEUED"
    assert scan["artifact_id"] == artifact["id"]
    
    # Wait for background task to complete
    scan_id = scan["id"]
    completed = False
    
    for _ in range(20):
        time.sleep(0.1)
        status_resp = client.get(f"/api/v1/projects/{project['id']}/scans/{scan_id}", headers=headers)
        assert status_resp.status_code == 200
        current_status = status_resp.json()["status"]
        if current_status == "COMPLETED":
            completed = True
            break
        elif current_status == "FAILED":
            pytest.fail("Scan failed")
            
    assert completed is True
    
    # Check dependencies via the scan result API
    final_scan = status_resp.json()
    assert final_scan["total_dependencies"] == 1
    
    # Also we should verify the dependencies directly if we had a deps endpoint,
    # but the total_dependencies counter confirms the parser ran successfully.

def test_scan_tenant_isolation(client):
    """Test user cannot create a scan for another org's project."""
    token1 = _register_and_login(client)
    token2 = _register_and_login(client)
    
    project1 = _create_project(client, token1)
    artifact1 = _create_artifact(client, token1, project1["id"])
    
    headers2 = {"Authorization": f"Bearer {token2}"}
    payload = {"artifact_id": artifact1["id"], "scan_type": "FULL"}
    
    resp = client.post(
        f"/api/v1/projects/{project1['id']}/scans",
        headers=headers2,
        json=payload
    )
    assert resp.status_code == 404

def test_scan_invalid_artifact(client):
    """Test user cannot create scan with non-existent artifact."""
    token = _register_and_login(client)
    project = _create_project(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {"artifact_id": str(uuid.uuid4()), "scan_type": "FULL"}
    resp = client.post(
        f"/api/v1/projects/{project['id']}/scans",
        headers=headers,
        json=payload
    )
    assert resp.status_code == 404

def test_get_project_graph(client):
    """Test retrieving dependency graph for a project."""
    token = _register_and_login(client)
    project = _create_project(client, token)
    artifact = _create_artifact(client, token, project["id"])
    headers = {"Authorization": f"Bearer {token}"}
    
    # Run scan
    client.post(
        f"/api/v1/projects/{project['id']}/scans",
        headers=headers,
        json={"artifact_id": artifact["id"], "scan_type": "FULL"}
    )
    
    # Poll for completion
    completed = False
    for _ in range(20):
        time.sleep(0.1)
        resp = client.get(f"/api/v1/projects/{project['id']}/graph", headers=headers)
        if resp.status_code == 200 and len(resp.json()["nodes"]) > 0:
            completed = True
            break
            
    assert completed is True
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) >= 2 # root + at least 1 dependency
    assert len(data["edges"]) >= 1
