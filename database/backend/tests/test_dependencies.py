"""Dependency API tests."""

import pytest
import time
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_dependencies_list_empty(client):
    from tests.test_scans import _register_and_login
    token = _register_and_login(client)
    
    resp = client.get(
        "/api/v1/dependencies",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []

def test_dependencies_list_and_detail(client):
    from tests.test_scans import _register_and_login, _create_project, _create_artifact
    
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create project and run scan
    proj = _create_project(client, token)
    artifact = _create_artifact(client, token, proj["id"])
    
    scan_resp = client.post(
        f"/api/v1/projects/{proj['id']}/scans",
        headers=headers,
        json={"artifact_id": artifact["id"], "scan_type": "FULL"}
    )
    assert scan_resp.status_code == 201
    
    completed = False
    for _ in range(20):
        time.sleep(0.1)
        st = client.get(f"/api/v1/projects/{proj['id']}/scans/{scan_resp.json()['id']}", headers=headers)
        if st.json()["status"] == "COMPLETED":
            completed = True
            break
            
    assert completed is True
    
    # 2. List dependencies
    resp = client.get("/api/v1/dependencies", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    
    item = data["items"][0]
    assert "id" in item
    assert "name" in item
    assert item["latestVersion"] == "N/A"
    assert item["healthScore"] == 0
    assert item["weeklyDownloads"] == 0
    
    # 3. Get details
    dep_id = item["id"]
    detail_resp = client.get(f"/api/v1/dependencies/{dep_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == dep_id
    assert detail["name"] == item["name"]
    assert detail["repository"] == proj["name"]
    assert "dependents" in detail

def test_dependencies_tenant_isolation(client):
    from tests.test_scans import _register_and_login, _create_project, _create_artifact
    
    token_a = _register_and_login(client)
    token_b = _register_and_login(client)
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    proj = _create_project(client, token_a)
    artifact = _create_artifact(client, token_a, proj["id"])
    
    scan_resp = client.post(
        f"/api/v1/projects/{proj['id']}/scans",
        headers=headers_a,
        json={"artifact_id": artifact["id"], "scan_type": "FULL"}
    )
    assert scan_resp.status_code == 201
    
    for _ in range(20):
        time.sleep(0.1)
        st = client.get(f"/api/v1/projects/{proj['id']}/scans/{scan_resp.json()['id']}", headers=headers_a)
        if st.json()["status"] == "COMPLETED":
            break
            
    # Tenant A should see dependencies
    resp_a = client.get("/api/v1/dependencies", headers=headers_a)
    assert resp_a.status_code == 200
    assert resp_a.json()["total"] > 0
    
    dep_id = resp_a.json()["items"][0]["id"]
    
    # Tenant B should see nothing
    resp_b = client.get("/api/v1/dependencies", headers=headers_b)
    assert resp_b.status_code == 200
    assert resp_b.json()["total"] == 0
    
    # Tenant B cannot access Tenant A's dependency detail
    detail_b = client.get(f"/api/v1/dependencies/{dep_id}", headers=headers_b)
    assert detail_b.status_code == 404

def test_dependencies_filters(client):
    from tests.test_scans import _register_and_login, _create_project, _create_artifact
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    proj = _create_project(client, token)
    artifact = _create_artifact(client, token, proj["id"])
    
    scan_resp = client.post(f"/api/v1/projects/{proj['id']}/scans", headers=headers, json={"artifact_id": artifact["id"], "scan_type": "FULL"})
    for _ in range(20):
        time.sleep(0.1)
        st = client.get(f"/api/v1/projects/{proj['id']}/scans/{scan_resp.json()['id']}", headers=headers)
        if st.json()["status"] == "COMPLETED":
            break

    # 1. Project filtering
    resp_proj = client.get(f"/api/v1/dependencies?project_id={proj['id']}", headers=headers)
    assert resp_proj.json()["total"] > 0

    # Dummy project ID returns 0
    import uuid
    resp_dummy = client.get(f"/api/v1/dependencies?project_id={str(uuid.uuid4())}", headers=headers)
    assert resp_dummy.json()["total"] == 0
    
    # 2. Status filtering (safe vs vulnerable)
    resp_safe = client.get("/api/v1/dependencies?status=safe", headers=headers)
    assert resp_safe.status_code == 200
    # ensure no items in safe have vulnerable status
    for item in resp_safe.json()["items"]:
        assert item["status"] == "safe"
        
    resp_vuln = client.get("/api/v1/dependencies?status=vulnerable", headers=headers)
    assert resp_vuln.status_code == 200
    for item in resp_vuln.json()["items"]:
        assert item["status"] == "vulnerable"
    # 3. Search query
    all_items_resp = client.get("/api/v1/dependencies", headers=headers)
    if all_items_resp.json()["total"] > 0:
        first_item_name = all_items_resp.json()["items"][0]["name"]
        resp_search = client.get(f"/api/v1/dependencies?query={first_item_name}", headers=headers)
        assert resp_search.json()["total"] > 0
        assert all(first_item_name.lower() in item["name"].lower() for item in resp_search.json()["items"])

def test_rbac_dependency(client):
    from tests.test_scans import _register_and_login
    token = _register_and_login(client)
    
    # In this test setup, registering gives the user OWNER role which has dependency.read.
    # So this should work.
    resp = client.get("/api/v1/dependencies", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
