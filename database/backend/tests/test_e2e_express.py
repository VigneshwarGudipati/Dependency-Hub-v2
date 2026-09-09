import asyncio
import time
import pytest
from fastapi.testclient import TestClient

from app.main import app

def test_real_end_to_end_express():
    client = TestClient(app)
    
    # 1. Register and login
    email = f"e2e_{int(time.time())}@test.com"
    client.post("/api/v1/auth/register", json={
        "name": "E2E Tester",
        "company": "E2E Corp",
        "email": email,
        "password": "StrongPass1!"
    })
    resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "StrongPass1!"
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Create Project
    print("\n[+] Creating project for Express...")
    create_resp = client.post("/api/v1/projects", json={
        "name": "express-e2e",
        "description": "E2E test",
        "language": "JavaScript",
        "visibility": "PRIVATE",
        "branch": "master",
        "url": "https://github.com/expressjs/express.git"
    }, headers=headers)
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]
    print(f"    Project ID: {project_id}")

    # 3. Trigger Repository Scan
    print("[+] Triggering Repository Scan...")
    scan_resp = client.post(f"/api/v1/projects/{project_id}/scans", json={
        "scan_type": "FULL"
    }, headers=headers)
    
    assert scan_resp.status_code == 201
    scan_data = scan_resp.json()
    scan_id = scan_data["id"]
    artifact_id = scan_data["artifact_id"]
    print(f"    Scan ID: {scan_id}")
    print(f"    Artifact ID generated: {artifact_id}")

    # Wait for scan to complete
    print("[+] Waiting for scan to complete...")
    for _ in range(30):
        status_resp = client.get(f"/api/v1/projects/{project_id}/scans/{scan_id}", headers=headers)
        if status_resp.json()["status"] in ["COMPLETED", "FAILED"]:
            break
        time.sleep(2)
        
    final_scan = client.get(f"/api/v1/projects/{project_id}/scans/{scan_id}", headers=headers).json()
    print(f"    Final Scan Status: {final_scan['status']}")
    assert final_scan["status"] == "COMPLETED"

    # 4. Check dependencies (Provenance check)
    print("[+] Verifying data provenance (Dependencies)...")
    graph_resp = client.get(f"/api/v1/projects/{project_id}/graph", headers=headers)
    assert graph_resp.status_code == 200
    graph_data = graph_resp.json()
    
    deps = graph_data.get("nodes", [])
    dep_names = [d.get("label", "Unknown") for d in deps]
    
    print(f"    Total dependencies found: {len(deps)}")
    print(f"    Sample dependencies: {dep_names[:5]}")
    
    # We should NOT see 'react' from the dummy project unless express uses react (it doesn't)
    assert "react" not in dep_names, "Data provenance failed: Dummy dependency 'react' was found!"
    
    # Express usually has 'accepts', 'array-flatten', 'body-parser', etc.
    assert any(name in dep_names for name in ["accepts", "body-parser", "cookie", "debug", "depd"]), "Expected Express dependencies not found!"
    print("    [PASS] No demo data found. Real dependencies acquired.")

    # 5. Check Report (Provenance check)
    print("[+] Generating and verifying report...")
    # Trigger report generation
    report_resp = client.post(f"/api/v1/projects/{project_id}/reports", json={
        "name": "E2E Report",
        "report_type": "PDF"
    }, headers=headers)
    assert report_resp.status_code == 201
    report_id = report_resp.json()["id"]
    
    for _ in range(30):
        r_status = client.get(f"/api/v1/projects/{project_id}/reports/{report_id}", headers=headers)
        if r_status.json()["status"] in ["READY", "FAILED"]:
            break
        time.sleep(2)
        
    final_report = client.get(f"/api/v1/projects/{project_id}/reports/{report_id}", headers=headers).json()
    assert final_report["status"] == "READY"
    print(f"    Report {report_id} generated successfully.")
    
    print("\nE2E VERIFICATION COMPLETE. ALL PROVENANCE INVARIANTS MET.")
