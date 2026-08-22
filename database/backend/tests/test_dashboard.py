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

def test_dashboard_empty_organization(client):
    """Test dashboard metrics for an organization with no projects or scans."""
    from tests.test_scans import _register_and_login
    token = _register_and_login(client)
    
    resp = client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["healthScore"] is None
    assert data["totalDependencies"] == 0
    assert data["safePackages"] == 0
    assert data["vulnerablePackages"] == 0
    assert data["scansThisWeek"] == 0
    assert data["activity"] == []


def test_dashboard_metrics(client):
    """Test dashboard metrics with real counts and vulnerabilities."""
    from tests.test_scans import _register_and_login, _create_project, _create_artifact
    
    # 1. Setup tenant A
    token_a = _register_and_login(client)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    proj = _create_project(client, token_a)
    
    # Artifact 1 (npm)
    artifact = _create_artifact(client, token_a, proj["id"])
    
    time.sleep(1)
    proj2 = _create_project(client, token_a)
    
    # Artifact 2 (PyPI)
    manifest = b'requests==2.28.1\nurllib3==1.26.12'
    files = {"file": ("requirements.txt", manifest, "text/plain")}
    pypi_resp = client.post(
        f"/api/v1/projects/{proj2['id']}/artifacts",
        headers={"Authorization": f"Bearer {token_a}"},
        files=files
    )
    artifact_pypi = pypi_resp.json()
    
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
    
    # Run scan 2 (PyPI)
    scan2_resp = client.post(
        f"/api/v1/projects/{proj2['id']}/scans",
        headers=headers_a,
        json={"artifact_id": artifact_pypi["id"], "scan_type": "FULL"}
    )
    assert scan2_resp.status_code == 201
    
    # Poll for completion 2
    completed2 = False
    for _ in range(20):
        time.sleep(0.1)
        st = client.get(f"/api/v1/projects/{proj2['id']}/scans/{scan2_resp.json()['id']}", headers=headers_a)
        if st.json()["status"] == "COMPLETED":
            completed2 = True
            break
            
    assert completed2 is True
    
    # 2. Get dashboard
    dash_resp = client.get("/api/v1/dashboard/summary", headers=headers_a)
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
    assert "PyPI" in ecosystems
    assert ecosystems["npm"] > 0
    assert ecosystems["PyPI"] > 0
    
    # Verify health score is None when no data allows computing it
    assert data["healthScore"] is None
    
    # 3. Setup tenant B (Isolation check)
    token_b = _register_and_login(client)
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    dash_b_resp = client.get("/api/v1/dashboard/summary", headers=headers_b)
    assert dash_b_resp.status_code == 200
    data_b = dash_b_resp.json()
    
    assert data_b["totalDependencies"] == 0
    assert data_b["scansThisWeek"] == 0
    assert len(data_b["activity"]) == 0
