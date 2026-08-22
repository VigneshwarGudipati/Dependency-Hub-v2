"""Phase 4: Member API tests."""

import time
import pytest
from fastapi.testclient import TestClient

from app.main import app

_counter = 0

def _unique_email():
    global _counter
    _counter += 1
    return f"memberuser{_counter}_{int(time.time())}@test.com"

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_list_members(client):
    email = _unique_email()
    # Register automatically creates an organization and assigns the user as owner
    client.post("/api/v1/auth/register", json={
        "name": "Member Tester",
        "company": f"Member Corp {_counter}",
        "email": email,
        "password": "StrongPass1!"
    })
    
    login_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "StrongPass1!"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = client.get("/api/v1/members", headers=headers)
    assert resp.status_code == 200
    members = resp.json()
    
    assert len(members) == 1
    assert members[0]["email"] == email
    assert members[0]["role"] == "OWNER"
    assert members[0]["status"] == "ACTIVE"
    assert "avatarColor" in members[0]
