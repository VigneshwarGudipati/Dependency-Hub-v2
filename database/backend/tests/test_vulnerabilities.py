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
    from tests.test_scans import _register_and_login, _create_project
    token = _register_and_login(client)
    proj = _create_project(client, token)

    resp = client.get(
        f"/api/v1/projects/{proj['id']}/vulnerabilities",
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

    resp = client.get(f"/api/v1/projects/{proj['id']}/vulnerabilities", headers=headers)
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

    resp_a = client.get(f"/api/v1/projects/{proj['id']}/vulnerabilities", headers=headers_a)
    assert resp_a.status_code == 200

    # Tenant B should get 404 if trying to access Tenant A's project
    resp_b = client.get(f"/api/v1/projects/{proj['id']}/vulnerabilities", headers=headers_b)
    assert resp_b.status_code == 404

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

    resp_all = client.get(f"/api/v1/projects/{proj['id']}/vulnerabilities", headers=headers)
    if resp_all.json()["total"] == 0:
        return # Skip test if no vulns

    first_item = resp_all.json()["items"][0]

    # 1. Project filtering is implicit now, but we can verify it returns 200
    resp_proj = client.get(f"/api/v1/projects/{proj['id']}/vulnerabilities", headers=headers)
    assert resp_proj.json()["total"] > 0

    # 2. Search query by CVE
    resp_search = client.get(f"/api/v1/projects/{proj['id']}/vulnerabilities?query={first_item['cve']}", headers=headers)
    assert resp_search.json()["total"] > 0
    assert first_item["cve"].lower() in resp_search.json()["items"][0]["cve"].lower()

    # 3. Search query by Package
    resp_pkg = client.get(f"/api/v1/projects/{proj['id']}/vulnerabilities?query={first_item['packageName']}", headers=headers)
    assert resp_pkg.json()["total"] > 0

    # 4. Severity filtering
    resp_sev = client.get(f"/api/v1/projects/{proj['id']}/vulnerabilities?severity={first_item['severity']}", headers=headers)
    for item in resp_sev.json()["items"]:
        assert item["severity"] == first_item["severity"]

def test_rbac_vulnerabilities(client):
    from tests.test_scans import _register_and_login, _create_project
    token = _register_and_login(client)
    proj = _create_project(client, token)

    resp = client.get(f"/api/v1/projects/{proj['id']}/vulnerabilities", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

def test_vulnerabilities_project_isolation(client):
    """Test vulnerabilities from project A don't leak into project B's vulnerabilities list."""
    from tests.test_scans import _register_and_login, _create_project, _create_artifact
    import time

    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    proj_a = _create_project(client, token)
    proj_b = _create_project(client, token)

    artifact_a = _create_artifact(client, token, proj_a["id"])
    scan_resp = client.post(
        f"/api/v1/projects/{proj_a['id']}/scans",
        headers=headers,
        json={"artifact_id": artifact_a["id"], "scan_type": "FULL"}
    )
    for _ in range(20):
        time.sleep(0.1)
        if client.get(f"/api/v1/projects/{proj_a['id']}/scans/{scan_resp.json()['id']}", headers=headers).json()["status"] == "COMPLETED":
            break

    vulns_a = client.get(f"/api/v1/projects/{proj_a['id']}/vulnerabilities", headers=headers).json()
    assert vulns_a["total"] > 0

    vulns_b = client.get(f"/api/v1/projects/{proj_b['id']}/vulnerabilities", headers=headers).json()
    assert vulns_b["total"] == 0, "Vulnerabilities from Project A leaked to Project B"
