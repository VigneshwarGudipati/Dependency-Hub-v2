import pytest
import time
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_reports_project_isolation(client):
    from tests.test_scans import _register_and_login, _create_project, _create_artifact
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
    scan_id = scan_resp.json()["id"]
    for _ in range(20):
        time.sleep(0.1)
        if client.get(f"/api/v1/projects/{proj_a['id']}/scans/{scan_id}", headers=headers).json()["status"] == "COMPLETED":
            break

    # Create report for proj A
    report_resp = client.post(
        f"/api/v1/projects/{proj_a['id']}/reports",
        headers=headers,
        json={"scan_id": scan_id, "format": "JSON"}
    )
    assert report_resp.status_code == 201
    report_id = report_resp.json()["id"]

    for _ in range(20):
        time.sleep(0.1)
        if client.get(f"/api/v1/projects/{proj_a['id']}/reports/{report_id}", headers=headers).json()["status"] == "COMPLETED":
            break

    # Now try to access the report using proj_b
    res_b = client.get(f"/api/v1/projects/{proj_b['id']}/reports/{report_id}", headers=headers)
    assert res_b.status_code == 404, "Project scoping not enforced on reports"

    # Also verify download isolation
    res_download = client.get(f"/api/v1/projects/{proj_b['id']}/reports/{report_id}/download", headers=headers)
    assert res_download.status_code == 404, "Project scoping not enforced on report downloads"
