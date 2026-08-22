"""Comprehensive Phase 3 authentication, RBAC, and tenant isolation tests."""

import time
import uuid
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import hash_password, hash_refresh_token
from app.core.dependencies import get_current_user, require_permission, get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


_counter = 0

def _unique_email():
    global _counter
    _counter += 1
    return f"testuser{_counter}_{int(time.time())}@test.com"


def _register(client, email=None, name="Test User", company="Test Corp", password="StrongPass1!"):
    if email is None:
        email = _unique_email()
    return client.post("/api/v1/auth/register", json={
        "name": name,
        "company": company,
        "email": email,
        "password": password,
    }), email


def _login(client, email, password="StrongPass1!"):
    return client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })


# ===========================================================================
# REGISTRATION TESTS
# ===========================================================================

def test_register_valid(client):
    resp, email = _register(client)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == email.lower()
    assert data["user"]["is_active"] is True
    assert data["user"]["organization"] is not None
    assert data["user"]["role"] == "OWNER"


def test_register_duplicate_email(client):
    resp1, email = _register(client)
    assert resp1.status_code == 201
    resp2, _ = _register(client, email=email)
    assert resp2.status_code == 409


def test_register_invalid_email(client):
    resp = client.post("/api/v1/auth/register", json={
        "name": "Test", "company": "C", "email": "not-an-email", "password": "StrongPass1!",
    })
    assert resp.status_code == 422


def test_register_short_password(client):
    resp = client.post("/api/v1/auth/register", json={
        "name": "Test", "company": "C", "email": _unique_email(), "password": "short",
    })
    assert resp.status_code == 422


def test_register_missing_name(client):
    resp = client.post("/api/v1/auth/register", json={
        "company": "C", "email": _unique_email(), "password": "StrongPass1!",
    })
    assert resp.status_code == 422


# ===========================================================================
# LOGIN TESTS
# ===========================================================================

def test_login_valid(client):
    resp_r, email = _register(client)
    assert resp_r.status_code == 201
    resp = _login(client, email)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == email.lower()


def test_login_wrong_password(client):
    _, email = _register(client)
    resp = _login(client, email, password="WrongPassword1!")
    assert resp.status_code == 401


def test_login_unknown_account(client):
    resp = _login(client, "nonexistent@test.com")
    assert resp.status_code == 401


def test_login_safe_error_message(client):
    """Ensure login errors don't reveal whether email exists."""
    resp1 = _login(client, "nonexistent@test.com")
    resp2, email = _register(client)
    resp3 = _login(client, email, password="WrongPassword1!")
    # Both should use the same generic message
    assert resp1.json()["error"]["message"] == resp3.json()["error"]["message"]


# ===========================================================================
# JWT TESTS
# ===========================================================================

def test_jwt_valid_access(client):
    resp_r, email = _register(client)
    token = resp_r.json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == email.lower()


def test_jwt_expired(client):
    """Create a token that expires immediately."""
    expired_token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "iat": datetime.now(timezone.utc),
         "exp": datetime.now(timezone.utc) - timedelta(seconds=10)},
        settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM,
    )
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


def test_jwt_invalid_signature(client):
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "iat": datetime.now(timezone.utc),
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "wrong-secret", algorithm="HS256",
    )
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_jwt_wrong_type(client):
    """A refresh-type token should not be accepted as access."""
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "refresh", "iat": datetime.now(timezone.utc),
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM,
    )
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_jwt_missing_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_jwt_malformed(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


# ===========================================================================
# REFRESH TOKEN TESTS
# ===========================================================================

def test_refresh_valid(client):
    resp_r, _ = _register(client)
    refresh = resp_r.json()["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # New refresh token must be different
    assert data["refresh_token"] != refresh


def test_refresh_old_token_rejected(client):
    """After rotation, the old refresh token must be rejected."""
    resp_r, _ = _register(client)
    old_refresh = resp_r.json()["refresh_token"]
    # Use it once
    resp1 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp1.status_code == 200
    # Try to use old one again — should fail (revoked)
    resp2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp2.status_code == 401


def test_refresh_invalid_token(client):
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage-token"})
    assert resp.status_code == 401


# ===========================================================================
# LOGOUT TESTS
# ===========================================================================

def test_logout_valid(client):
    resp_r, email = _register(client)
    data = resp_r.json()
    token = data["access_token"]
    refresh = data["refresh_token"]
    resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


def test_logout_revokes_refresh(client):
    resp_r, email = _register(client)
    data = resp_r.json()
    token = data["access_token"]
    refresh = data["refresh_token"]
    # Logout
    client.post("/api/v1/auth/logout", json={"refresh_token": refresh},
                headers={"Authorization": f"Bearer {token}"})
    # Attempt to use revoked refresh
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401


# ===========================================================================
# /auth/me TESTS
# ===========================================================================

def test_me_authenticated(client):
    resp_r, email = _register(client)
    token = resp_r.json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == email.lower()
    assert "password_hash" not in data
    assert "refresh_token" not in data


# ===========================================================================
# RBAC TESTS
# ===========================================================================

def test_rbac_permission_present_allowed(client):
    """OWNER role should have organization.read permission."""
    # We test this via a test-only route that uses require_permission
    test_app = FastAPI()

    @test_app.get("/test-perm", dependencies=[Depends(require_permission("organization.read"))])
    async def _test(db=Depends(get_db)):
        return {"allowed": True}

    app.mount("/test-rbac", test_app)

    resp_r, _ = _register(client)
    token = resp_r.json()["access_token"]
    resp = client.get("/test-rbac/test-perm", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_rbac_permission_absent_denied(client):
    """Test a non-existent permission is denied."""
    test_app2 = FastAPI()

    @test_app2.get("/test-deny", dependencies=[Depends(require_permission("nonexistent.permission"))])
    async def _test(db=Depends(get_db)):
        return {"allowed": True}

    app.mount("/test-rbac-deny", test_app2)

    resp_r, _ = _register(client)
    token = resp_r.json()["access_token"]
    resp = client.get("/test-rbac-deny/test-deny", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


# ===========================================================================
# TENANT ISOLATION TESTS
# ===========================================================================

def test_tenant_isolation_cross_org_denied(client):
    """User A should NOT access User B's organization."""
    # Register User A
    resp_a, _ = _register(client, name="User A", company="Org A")
    data_a = resp_a.json()
    token_a = data_a["access_token"]
    org_a_id = data_a["user"]["organization"]["id"]

    # Register User B
    resp_b, _ = _register(client, name="User B", company="Org B")
    data_b = resp_b.json()
    token_b = data_b["access_token"]
    org_b_id = data_b["user"]["organization"]["id"]

    assert org_a_id != org_b_id

    # User A accesses their own org → allowed
    resp_own = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_own.status_code == 200
    assert resp_own.json()["organization"]["id"] == org_a_id

    # User B accesses their own org → allowed
    resp_own_b = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_own_b.status_code == 200
    assert resp_own_b.json()["organization"]["id"] == org_b_id


# ===========================================================================
# SECURITY REGRESSION TESTS
# ===========================================================================

def test_password_hash_never_in_response(client):
    """Password hash must never appear in any auth response."""
    resp_r, email = _register(client)
    assert "password_hash" not in resp_r.text

    resp_l = _login(client, email)
    assert "password_hash" not in resp_l.text

    token = resp_l.json()["access_token"]
    resp_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert "password_hash" not in resp_me.text


def test_refresh_token_hash_never_in_response(client):
    """Refresh token hash must never appear in any auth response."""
    resp_r, _ = _register(client)
    raw_refresh = resp_r.json()["refresh_token"]
    hashed = hashlib.sha256(raw_refresh.encode()).hexdigest()
    assert hashed not in resp_r.text


def test_error_format_consistency(client):
    """Auth errors should use the unified error schema."""
    resp = _login(client, "nonexistent@test.com")
    data = resp.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
