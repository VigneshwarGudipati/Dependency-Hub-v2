# Dependency Hub Test Suite Structure

Dependency Hub maintains two independent test suites. They are deliberately separated to avoid module collection collisions and to isolate database-level persistence tests from API-level HTTP tests.

## DB Layer
**Path**: `database/tests/`

**Purpose**: Database, model, constraint, relationship, and multitenancy verification.
These tests use SQLAlchemy async sessions with per-test transaction rollbacks. They verify that the database schema correctly enforces business rules before the API layer is involved.

**Command**:
```powershell
cd database
$env:PYTHONPATH="backend"
pytest -v tests
```

## API Layer
**Path**: `database/backend/tests/`

**Purpose**: FastAPI HTTP/API verification.
These tests use the FastAPI `TestClient` to verify HTTP endpoints, authentication (JWT), RBAC, tenant isolation at the request level, and API response contracts.

**Command**:
```powershell
cd database
$env:PYTHONPATH="backend"
pytest -v backend/tests
```

## Full Verification

To run the complete verification suite (which runs both test suites explicitly, followed by frontend build and lint):

```powershell
.\scripts\verify.ps1
```

**Why are the suites separated?**
The initial repository consolidation combined both paths into the automatic `testpaths` configuration in `pytest.ini`. However, both directories contain tests with identical basenames (e.g., `test_artifacts.py`, `test_multitenancy.py`). When pytest attempts to collect them globally, it results in an `import file mismatch` error due to module namespace collisions. By executing each suite explicitly, we preserve their valid duplicate naming without requiring arbitrary file renaming or complex Python import hacks.
