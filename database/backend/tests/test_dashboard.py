"""Dashboard tests."""

import pytest
import time
from httpx import AsyncClient
from fastapi.testclient import TestClient
from app.models.vulnerability import SeverityLevel
from app.models.scan import ScanStatus
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_dashboard_empty_project(client):
    """Test dashboard metrics for an organization with a project but no scans."""
    from tests.test_scans import _register_and_login, _create_project
    token = _register_and_login(client)
    proj = _create_project(client, token)

    resp = client.get(
        f"/api/v1/projects/{proj['id']}/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["healthScore"] is None
    assert data["totalDependencies"] == 0
    assert data["safePackages"] == 0
    assert data["vulnerablePackages"] == 0
    assert data["scansThisWeek"] == 0
    # Audit logs are currently still org-scoped but let's just assert activity is a list
    assert isinstance(data["activity"], list)


def test_dashboard_metrics(client):
    """Test dashboard metrics with real counts and vulnerabilities."""
    from tests.test_scans import _register_and_login, _create_project, _create_artifact

    # 1. Setup tenant A
    token_a = _register_and_login(client)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    proj = _create_project(client, token_a)

    # Artifact 1 (npm)
    artifact = _create_artifact(client, token_a, proj["id"])

    # Run scan 1 (npm)
    scan_resp = client.post(
        f"/api/v1/projects/{proj['id']}/scans",
        headers=headers_a,
        json={"artifact_id": artifact["id"], "scan_type": "FULL"}
    )
    assert scan_resp.status_code == 201

    # Poll for completion
    completed = False
    for _ in range(20):
        time.sleep(0.1)
        st = client.get(f"/api/v1/projects/{proj['id']}/scans/{scan_resp.json()['id']}", headers=headers_a)
        if st.json()["status"] == "COMPLETED":
            completed = True
            break

    assert completed is True

    # 2. Get dashboard
    dash_resp = client.get(f"/api/v1/projects/{proj['id']}/dashboard/summary", headers=headers_a)
    assert dash_resp.status_code == 200
    data = dash_resp.json()

    assert data["totalDependencies"] > 0
    assert data["vulnerablePackages"] >= 0
    assert data["safePackages"] == data["totalDependencies"] - data["vulnerablePackages"]
    assert data["scansThisWeek"] >= 1
    assert len(data["severityBreakdown"]) == 4 # CRITICAL, HIGH, MEDIUM, LOW
    assert len(data["activity"]) >= 1 # Scan created, etc

    # Verify Ecosystem breakdown
    ecosystems = {e["label"]: e["value"] for e in data["ecosystemBreakdown"]}
    assert "npm" in ecosystems
    assert ecosystems["npm"] > 0

    # Verify health score is None when no data allows computing it
    assert data["healthScore"] is None

    # 3. Setup tenant B (Isolation check)
    token_b = _register_and_login(client)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    dash_b_resp = client.get(f"/api/v1/projects/{proj['id']}/dashboard/summary", headers=headers_b)
    # Project doesn't belong to Tenant B, should be 404
    assert dash_b_resp.status_code == 404

def test_dashboard_project_isolation_strict(client):
    """Test dashboard metrics are isolated strictly to the requested project."""
    from tests.test_scans import _register_and_login, _create_project, _create_artifact
    import time

    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    proj_a = _create_project(client, token)
    proj_b = _create_project(client, token)

    # Run scan on proj A
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

    # Proj A dashboard has data
    dash_a = client.get(f"/api/v1/projects/{proj_a['id']}/dashboard/summary", headers=headers).json()
    assert dash_a["totalDependencies"] > 0

    # Proj B dashboard must be completely empty, no leakage from Proj A
    dash_b = client.get(f"/api/v1/projects/{proj_b['id']}/dashboard/summary", headers=headers).json()
    assert dash_b["totalDependencies"] == 0, "Project A dependencies leaked to Project B dashboard"
    assert dash_b["scansThisWeek"] == 0
