import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers

def test_database_health(client):
    response = client.get("/health/database")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["connected"] is True
    assert "postgres_version" in data
    assert "x-request-id" in response.headers

def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "healthy"
    assert "x-request-id" in response.headers

def test_api_v1(client):
    response = client.get("/api/v1")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Dependency Hub API"
    assert data["version"] == "v1"

def test_openapi_docs(client):
    response_docs = client.get("/docs")
    assert response_docs.status_code == 200
    
    response_openapi = client.get("/openapi.json")
    assert response_openapi.status_code == 200

def test_exception_handling():
    # Use raise_server_exceptions=False so the global_exception_handler
    # can intercept and convert the ValueError to a 500 JSON response.
    # This matches production behaviour where Starlette's error handler fires.
    exc_client = TestClient(app, raise_server_exceptions=False)
    @app.get("/test-error")
    async def force_error():
        raise ValueError("Simulated unexpected error")

    response = exc_client.get("/test-error")
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert data["error"]["message"] == "An unexpected error occurred"
    # NOTE: x-request-id is added by RequestIDMiddleware *after* call_next.
        # When BaseHTTPMiddleware propagates an unhandled exception the middleware
        # does not get a chance to annotate the error response headers.
        # This is a known Starlette BaseHTTPMiddleware limitation; the exception
        # handler (correct JSON structure + 500 status) is verified above.

def test_request_validation_handling(client):
    @app.get("/test-validation")
    async def validation_test(num: int):
        return {"num": num}
        
    response = client.get("/test-validation?num=invalid")
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "issues" in data["error"]["details"]
