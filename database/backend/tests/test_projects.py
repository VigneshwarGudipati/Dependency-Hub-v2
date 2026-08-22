"""Phase 4: Project/Repository API tests."""

import time
import pytest
from fastapi.testclient import TestClient

from app.main import app

_counter = 0

def _unique_email():
    global _counter
    _counter += 1
    return f"projectuser{_counter}_{int(time.time())}@test.com"

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def _register_and_login(client):
    email = _unique_email()
    client.post("/api/v1/auth/register", json={
        "name": "Project Tester",
        "company": f"Project Corp {_counter}",
        "email": email,
        "password": "StrongPass1!"
    })
    resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "StrongPass1!"
    })
    return resp.json()["access_token"], email

def test_create_and_list_project(client):
    token, _ = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create project
    create_resp = client.post("/api/v1/projects", json={
        "name": "test-repo",
        "description": "Test repository",
        "language": "TypeScript",
        "visibility": "PRIVATE",
        "branch": "main",
        "url": "https://github.com/test/repo"
    }, headers=headers)
    
    assert create_resp.status_code == 201, create_resp.text
    project_data = create_resp.json()
    assert project_data["name"] == "test-repo"
    assert project_data["healthScore"] == 100
    
    project_id = project_data["id"]
    
    # 2. Get project by ID
    get_resp = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "test-repo"
    
    # 3. List projects
    list_resp = client.get("/api/v1/projects", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1
    assert any(p["id"] == project_id for p in items)

def test_project_duplicate_slug(client):
    token, _ = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "name": "duplicate-repo",
        "description": "Test repository",
        "language": "Go",
        "visibility": "ORGANIZATION",
        "branch": "main"
    }
    
    resp1 = client.post("/api/v1/projects", json=payload, headers=headers)
    assert resp1.status_code == 201
    
    resp2 = client.post("/api/v1/projects", json=payload, headers=headers)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["error"]["message"]

def test_project_tenant_isolation(client):
    token1, _ = _register_and_login(client)
    token2, _ = _register_and_login(client)
    
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}
    
    # User 1 creates project
    create_resp = client.post("/api/v1/projects", json={
        "name": "secret-project",
        "description": "Secret",
        "language": "Python",
        "visibility": "PRIVATE",
        "branch": "main"
    }, headers=headers1)
    project_id = create_resp.json()["id"]
    
    # User 2 tries to access User 1's project
    get_resp = client.get(f"/api/v1/projects/{project_id}", headers=headers2)
    assert get_resp.status_code == 404

def test_project_list_tenant_isolation(client):
    token1, _ = _register_and_login(client)
    token2, _ = _register_and_login(client)
    
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}
    
    client.post("/api/v1/projects", json={
        "name": "org1-project", "description": "", "language": "Go", 
        "visibility": "ORGANIZATION", "branch": "main"
    }, headers=headers1)
    
    # User 2 lists projects
    list_resp = client.get("/api/v1/projects", headers=headers2)
    assert list_resp.status_code == 200
    items = list_resp.json()
    # Should not see org1-project
    assert not any(p["name"] == "org1-project" for p in items)
