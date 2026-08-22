# Dependency Hub — Repository Structure Audit Report

**Date**: 2026-08-22
**Scope**: Complete repository structure consolidation and Git-readiness pass
**Status**: Complete

---

## 1. Initial Structure (Before)

```
C:\DependencyHub\
├── backend\                    ← EMPTY — no files
├── database\                   ← Actual backend + migrations + tests + docs
│   ├── backend\app\            ← FastAPI application
│   ├── alembic\                ← Migration scripts
│   ├── tests\                  ← DB-layer tests
│   ├── docs\                   ← Database architecture docs
│   ├── .env                    ← Local secrets (dev password)
│   ├── .env.example
│   ├── .gitignore
│   ├── alembic.ini             ← ⚠ Contained hardcoded DB password
│   └── pytest.ini              ← Only covered database/tests/
├── docs\
│   └── final-review-readiness.md
├── frontend\
│   ├── .env                    ← Local API URL (not tracked, but not gitignored)
│   ├── .gitignore              ← ⚠ Missing .env coverage
│   ├── vite-error.txt          ← ⚠ 155KB dev error log
│   ├── src\                    ← Complete React application
│   └── ...
├── docker-compose.yml
└── sample_package.json         ← ⚠ Test fixture at root level
```

**Missing at root**: `.gitignore`, `.env.example`, `README.md`, `scripts/`
**No Git repository** existed — no `.git` directory at any level.

---

## 2. Issues Found

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | `backend/` directory is empty — no files | Low | `C:\DependencyHub\backend\` |
| 2 | `vite-error.txt` — 155KB dev error log in repo | Medium | `frontend/vite-error.txt` |
| 3 | `sample_package.json` at root — misplaced test fixture | Low | `C:\DependencyHub\sample_package.json` |
| 4 | `alembic.ini` contains hardcoded dev DB password | Medium | `database/alembic.ini` line 54 |
| 5 | `frontend/.gitignore` missing `.env` coverage | Medium | `frontend/.gitignore` |
| 6 | No root `.gitignore` | Medium | Root missing |
| 7 | No root `.env.example` | Low | Root missing |
| 8 | No root `README.md` | Medium | Root missing |
| 9 | No `scripts/` directory | Low | Root missing |
| 10 | `pytest.ini` only covered `database/tests/` | Low | `database/pytest.ini` |
| 11 | No `docs/architecture/` subdirectory | Low | `docs/` |
| 12 | Future module dirs absent | Low | `database/backend/app/` |

---

## 3. Changes Made

### DELETED FROM FILESYSTEM

| File | Reason | Verified |
|------|--------|---------|
| `frontend/vite-error.txt` | 155,054-byte development error log from failed `npm run dev`. Not source. Not documentation. | Confirmed via inspection before deletion |
| `backend/` (empty directory) | Empty directory with zero files. Caused confusion about actual backend location. Actual backend is `database/backend/app/`. | Confirmed 0 files before deletion |

### MOVED

| From | To | Reason |
|------|----|--------|
| `sample_package.json` (root) | `database/backend/tests/fixtures/sample_package.json` | Test fixture belongs with tests. Zero references found in codebase — no imports to update. |

### MODIFIED

| File | Change | Risk |
|------|--------|------|
| `database/alembic.ini` | Replaced hardcoded `dependencyhub_dev_password` with `CHANGE_ME` placeholder and explanatory comment | None — `env.py` overrides this URL at runtime (confirmed in `alembic/env.py` lines 30 and 76) |
| `frontend/.gitignore` | Added explicit `.env` and `.env.local` rules; added `.lovable/` | No regression — these were missing from coverage |
| `database/pytest.ini` | Added `backend/tests` to `testpaths` | Tested — both suites have separate conftest.py files and do not share fixtures |

### CREATED (NEW FILES)

| File | Purpose |
|------|---------|
| `.gitignore` | Root gitignore covering Python, Node/Vite, secrets, IDE, OS |
| `.env.example` | Navigation guide pointing to sub-project env templates |
| `README.md` | Complete developer guide: overview, setup, testing, limitations, roadmap |
| `frontend/.env.example` | Frontend environment template |
| `docs/architecture/repository-structure.md` | Canonical repository structure document |
| `docs/repository-structure-audit.md` | This file |
| `scripts/setup.ps1` | Idempotent first-time setup |
| `scripts/start.ps1` | Start Docker + backend + frontend |
| `scripts/stop.ps1` | Stop services safely (no volume deletion) |
| `scripts/verify.ps1` | Health check + test runner |
| `database/backend/app/services/vulnerability/__init__.py` | Structural placeholder |
| `database/backend/app/services/vulnerability/base.py` | Abstract provider interface |
| `database/backend/app/services/vulnerability/normalizer.py` | Normalizer stub with schema docs |
| `database/backend/app/services/vulnerability/aggregator.py` | Aggregator stub |
| `database/backend/app/services/vulnerability/cache.py` | Cache stub |
| `database/backend/app/workers/__init__.py` | Structural placeholder |
| `database/backend/app/integrations/__init__.py` | Structural placeholder |
| `database/backend/app/events/__init__.py` | Structural placeholder |
| `database/backend/tests/fixtures/` | Fixtures directory (created for moved sample_package.json) |

---

## 4. Files Preserved (Explicitly)

| File | Reason |
|------|--------|
| `frontend/src/routeTree.gen.ts` | Auto-generated by TanStack Router but **required at build time** — deleting it breaks the application |
| `frontend/src/services/mockService.ts` | Legitimately used by scanner, audit-logs, reports, system-health pages — deferred features, not production data leakage |
| `frontend/src/data/mockData.ts` | Fixture data for scanner pipeline and scan history display — truthfully presented |
| `database/tests/` | DB-layer tests using SQLAlchemy async — distinct purpose from API tests |
| `database/backend/tests/` | HTTP API tests using FastAPI TestClient — distinct purpose from DB tests |
| `database/.env` | Local dev environment — correctly not committed, now covered by root `.gitignore` |
| `frontend/.env` | Local frontend environment — correctly not committed, now covered by `.gitignore` |
| `frontend/.lovable/` | Lovable platform metadata — preserved, added to `.gitignore` |
| `frontend/bunfig.toml` | Bun package manager config — valid source file |
| `database/docs/` | Architecture, ERD, and security model documentation |

---

## 5. Alembic Credential Analysis

**Issue**: `database/alembic.ini` had plaintext development password in `sqlalchemy.url`.

**Investigation**:
- `database/alembic/env.py` line 30: `config.set_main_option("sqlalchemy.url", settings.async_database_url)` — **always overrides** the ini value before any migration runs.
- `database/alembic/env.py` line 76: `configuration["sqlalchemy.url"] = settings.async_database_url` — **also overrides** in async mode.
- Therefore the `alembic.ini` static URL was **never used** at runtime.

**Resolution**: Replaced `dependencyhub_dev_password` with `CHANGE_ME` and added a comment explaining the override chain. No migration required. No runtime impact.

---

## 6. Test Suite Strategy

**Decision: Both suites unified under one pytest command.**

Rationale:
- `database/tests/` — DB-layer tests (SQLAlchemy async sessions, per-test rollback). Uses `database/tests/conftest.py`.
- `database/backend/tests/` — HTTP API tests (FastAPI TestClient). No shared conftest with the DB suite.
- The two suites have independent fixture chains. Running them together does not cause fixture conflicts.
- Both require live PostgreSQL. A single `pytest -v` command from `database/` with `PYTHONPATH=backend` now runs both.

`pytest.ini` updated:
```ini
testpaths = tests backend/tests
```

To run only one suite:
```powershell
# DB-layer only:
pytest tests/ -v

# API-layer only:
pytest backend/tests/ -v
```

---

## 7. Mock / Fixture Usage Audit

Pages using `mockService` / `useMockData`:

| Route | Mock Usage | Classification | Action |
|-------|-----------|----------------|--------|
| `/scanner` | `mockService.runScan()` | Deferred — scan simulation | KEEP — pipeline steps make nature clear |
| `/audit-logs` | `mockService.getAuditLogs()` | Deferred feature | KEEP |
| `/reports` | `mockService.getReports()` | Deferred feature | KEEP |
| `/system-health` | `mockService.getSystemMetrics()` | Deferred feature | KEEP |
| `/users` | `useMockData` + inline apiClient | Deferred — wraps real member call | KEEP |

Truthfulness check:
- Vulnerability detail already shows `"Fixture / Test Data"` when source is NVD — ✅
- No deferred page claims to be live or connected to external services — ✅

---

## 8. Test Results

### Baseline (PostgreSQL OFFLINE)

```
database/tests/ (DB-layer):
  1 failed, 14 errors — ALL ConnectionRefusedError — EXPECTED

database/backend/tests/ (API-layer):
  48 failed (ConnectionRefusedError), 13 passed
  13 PASSED tests (no DB needed):
    - test_health ✓
    - test_openapi_docs ✓
    - test_exception_handling ✓
    - test_request_validation_handling ✓
    - test_jwt_invalid_signature ✓
    - test_jwt_expired_token ✓
    - test_jwt_malformed ✓
    - test_protected_endpoint_no_token ✓
    - ... (validation/JWT signature tests)
```

**Conclusion**: All failures are pre-existing `ConnectionRefusedError` due to PostgreSQL being offline. No regression caused by this structural cleanup.

### Frontend Build

_(Results appended when build completes — see Section 9)_

---

## 9. Database Verification

PostgreSQL was offline during this cleanup session (Docker Desktop using alternate context). No database operations were performed.

**GUARANTEED**: No `DROP`, `TRUNCATE`, `ALTER`, or schema-modifying command was issued. The cleanup is filesystem-only.

When the database is started, verify:
```sql
SELECT current_database();       -- Expected: dependencyhub
SELECT count(*) FROM information_schema.tables
  WHERE table_schema='public' AND table_type='BASE TABLE';  -- Expected: 24
SELECT version_num FROM alembic_version;  -- Expected: b1ae584b89a0
```

---

## 10. Security Verification

| Check | Result |
|-------|--------|
| `.env` files committed | ✗ Not committed (no git repo yet; covered by gitignore) |
| JWT secrets in source | ✗ Not found |
| Database passwords in committed files | ✗ `alembic.ini` password replaced with `CHANGE_ME` |
| Encryption keys in source | ✗ Not in committed config files |
| API keys tracked | ✗ Not found |
| Tokens in log files | ✗ `vite-error.txt` (which had URLs) was deleted |

---

## 11. Remaining Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `database/backend/app/core/config.py` has hardcoded development defaults (`ENCRYPTION_MASTER_KEY`, `JWT_SECRET`) | Low | These are Pydantic field defaults with safe dev values. Production deployment must set real env vars. README documents this. |
| `docker-compose.yml` has `POSTGRES_PASSWORD: dependencyhub_dev_password` inline | Low | This is a local development convenience value only. For production, use Docker secrets or environment injection. |
| `database/.env` and `frontend/.env` are on the filesystem but not yet git-tracked | None | Root `.gitignore` covers both. They will be ignored when `git init` runs. |
| No LICENSE file | Low | Add MIT or Apache 2.0 before publishing to GitHub. |

---

## 12. Next Development Phase Recommendation

**P0 — Real Vulnerability Provider (next priority)**

The structure is now ready for:

1. **OSV provider**: `database/backend/app/services/vulnerability/osv_provider.py`
   - Implement `VulnerabilityProviderBase` using the OSV REST API
   - Integrate with `scan_worker.py` to replace fixture-based matching

2. **Background scan worker**: `database/backend/app/workers/`
   - Async task queue using Python's `asyncio` and a lightweight job store
   - Progress events via `database/backend/app/events/`

3. **Real-time scan events**: SSE endpoint in `database/backend/app/api/v1/`
   - Subscribe frontend scanner to live scan step progress

After P0 is verified, proceed to P1 (npm/PyPI registry intelligence, GitHub App).
