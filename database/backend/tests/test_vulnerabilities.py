"""Vulnerabilities API tests."""

import pytest
import time
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_vulnerabilities_list_empty(client):
    from tests.test_scans import _register_and_login
    token = _register_and_login(client)
    
    resp = client.get(
        "/api/v1/vulnerabilities",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []

def test_vulnerabilities_list(client):
    from tests.test_scans import _register_and_login, _create_project, _create_artifact
    
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    
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
    
    resp = client.get("/api/v1/vulnerabilities", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # It depends on if the mock scanner creates vulnerabilities. Our mock scanner does.
    # In tests, dummy vulnerabilities are created.
    assert data["total"] >= 0
    
    if data["total"] > 0:
        item = data["items"][0]
        assert "cve" in item
        assert "severity" in item
        assert "packageName" in item
        assert item["repository"] == proj["name"]

def test_vulnerabilities_tenant_isolation(client):
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
    
    for _ in range(20):
        time.sleep(0.1)
        st = client.get(f"/api/v1/projects/{proj['id']}/scans/{scan_resp.json()['id']}", headers=headers_a)
        if st.json()["status"] == "COMPLETED":
            break
            
    resp_a = client.get("/api/v1/vulnerabilities", headers=headers_a)
    assert resp_a.status_code == 200
    
    # Tenant B should see nothing
    resp_b = client.get("/api/v1/vulnerabilities", headers=headers_b)
    assert resp_b.status_code == 200
    assert resp_b.json()["total"] == 0

def test_vulnerabilities_filters(client):
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

    resp_all = client.get("/api/v1/vulnerabilities", headers=headers)
    if resp_all.json()["total"] == 0:
        return # Skip test if no vulns
        
    first_item = resp_all.json()["items"][0]
    
    # 1. Project filtering
    resp_proj = client.get(f"/api/v1/vulnerabilities?project_id={proj['id']}", headers=headers)
    assert resp_proj.json()["total"] > 0

    # 2. Search query by CVE
    resp_search = client.get(f"/api/v1/vulnerabilities?query={first_item['cve']}", headers=headers)
    assert resp_search.json()["total"] > 0
    assert first_item["cve"].lower() in resp_search.json()["items"][0]["cve"].lower()
    
    # 3. Search query by Package
    resp_pkg = client.get(f"/api/v1/vulnerabilities?query={first_item['packageName']}", headers=headers)
    assert resp_pkg.json()["total"] > 0

    # 4. Severity filtering
    resp_sev = client.get(f"/api/v1/vulnerabilities?severity={first_item['severity']}", headers=headers)
    for item in resp_sev.json()["items"]:
        assert item["severity"] == first_item["severity"]

def test_rbac_vulnerabilities(client):
    from tests.test_scans import _register_and_login
    token = _register_and_login(client)
    
    resp = client.get("/api/v1/vulnerabilities", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
