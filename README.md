# Dependency Hub

> **Monitor. Analyze. Secure.**
> A multi-tenant software dependency health and security platform.

Dependency Hub provides portfolio-wide visibility into open-source dependency risk. It scans manifest files, catalogs CVEs, tracks package health scores, and surfaces actionable security findings across every repository in your organisation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (TanStack Start)              │
│  React 19 · TanStack Router · TanStack Query · Vite 8   │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP/REST  /api/v1
┌──────────────────────────▼──────────────────────────────┐
│               FastAPI Backend (Python 3.14)              │
│  SQLAlchemy 2.x · asyncpg · JWT · RBAC · Alembic        │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│           PostgreSQL 16  (Docker container)              │
│  24 tables · multi-tenant · envelope encryption         │
└─────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
DependencyHub/
│
├── frontend/                  # TanStack Start (SSR) React application
│   ├── src/
│   │   ├── components/        # Reusable UI components (charts, layout, ui)
│   │   ├── data/              # Test fixtures and mock data
│   │   ├── hooks/             # React Query hooks (useProjects, useAuth, …)
│   │   ├── lib/               # Utilities and error reporting helpers
│   │   ├── routes/            # File-based routes (TanStack Router)
│   │   ├── services/
│   │   │   └── apiClient.ts   # ← Canonical centralized API client
│   │   ├── types/             # Shared TypeScript types
│   │   └── utils/             # Formatting helpers
│   ├── public/                # Static assets
│   ├── .env.example           # Frontend environment template
│   ├── package.json
│   └── vite.config.ts
│
├── database/                  # Backend, migrations, and database layer
│   ├── backend/
│   │   ├── app/               # FastAPI application
│   │   │   ├── api/           # HTTP route handlers
│   │   │   ├── core/          # Config, DB session, security, middleware
│   │   │   ├── models/        # SQLAlchemy ORM models (23 domain tables)
│   │   │   ├── repositories/  # Database access abstractions
│   │   │   ├── schemas/       # Pydantic request/response schemas
│   │   │   ├── services/      # Business logic services
│   │   │   │   └── vulnerability/ # (Future: OSV/NVD providers)
│   │   │   ├── workers/       # (Future: background scan workers)
│   │   │   ├── integrations/  # (Future: GitHub, registry providers)
│   │   │   ├── events/        # (Future: SSE/real-time event bus)
│   │   │   └── main.py        # FastAPI application entrypoint
│   │   ├── tests/             # HTTP API tests (FastAPI TestClient)
│   │   └── requirements.txt
│   ├── alembic/               # Database migration scripts
│   │   └── versions/
│   │       └── b1ae584b89a0_0001_initial_database_schema.py
│   ├── tests/                 # Database-layer tests (SQLAlchemy async)
│   ├── docs/                  # Architecture, ERD, and security model docs
│   ├── .env.example           # Backend environment template
│   ├── alembic.ini
│   └── pytest.ini
│
├── docs/                      # Project-level documentation
│   ├── architecture/          # Architecture and structure docs
│   ├── final-review-readiness.md
│   └── repository-structure-audit.md
│
├── scripts/                   # PowerShell developer scripts
│   ├── setup.ps1              # Install dependencies and create .venv
│   ├── start.ps1              # Start Docker, backend, and frontend
│   ├── stop.ps1               # Stop services (no data loss)
│   └── verify.ps1             # Health check and test runner
│
├── .gitignore                 # Root gitignore (Python + Node + secrets)
├── .env.example               # Environment guide (points to sub-templates)
├── docker-compose.yml         # PostgreSQL 16 container
└── README.md                  # This file
```

---

## Prerequisites

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Docker Desktop | Latest | PostgreSQL container |
| Python | 3.12+ | Backend runtime |
| Node.js | 20+ | Frontend runtime |
| npm | 10+ | Frontend package manager |

---

## Environment Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd DependencyHub
```

### 2. Configure backend environment

```powershell
Copy-Item database\.env.example database\.env
# Edit database\.env and set your POSTGRES_PASSWORD, JWT_SECRET, ENCRYPTION_MASTER_KEY
```

### 3. Configure frontend environment

```powershell
Copy-Item frontend\.env.example frontend\.env
# Default value (VITE_API_BASE_URL=http://localhost:8000/api/v1) works for local dev
```

---

## Docker / PostgreSQL

```powershell
# Start PostgreSQL container (defined in docker-compose.yml)
docker compose up -d

# Verify container health
docker compose ps
```

The PostgreSQL container exposes port **5432** and uses a persistent named volume (`dependencyhub_postgres_data`).

> **⚠ Never run `docker compose down -v`** — this permanently deletes database data.

---

## Backend Setup

```powershell
cd database

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend/requirements.txt

# Apply database migrations
$env:PYTHONPATH="backend"; alembic upgrade head

# (Optional) Seed reference data
$env:PYTHONPATH="backend"; python backend/app/seed.py

# Start the backend
$env:PYTHONPATH="backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Backend is available at:
- **API**: http://localhost:8000/api/v1
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health**: http://localhost:8000/health

---

## Frontend Setup

```powershell
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend dev server starts on the port Vite assigns (default **3000** for TanStack Start). Check the terminal output for the exact URL.

---

## Running Tests & Test Suite Organization

Dependency Hub uses two distinct, independent test suites. They are deliberately separated to prevent module collection collisions (because both suites use identical file basenames like `test_artifacts.py`) and to isolate testing domains.

### 1. Database-layer tests (requires running PostgreSQL)

**Path:** `database/tests/`
**Purpose:** Verifies SQLAlchemy models, constraints, relationships, and multi-tenancy rules using async sessions directly against PostgreSQL (with per-test transaction rollbacks).

```powershell
cd database
$env:PYTHONPATH="backend"
.\.venv\Scripts\pytest.exe -v tests
```

### 2. API-layer tests (requires running PostgreSQL)

**Path:** `database/backend/tests/`
**Purpose:** Verifies the full FastAPI application via `TestClient`. Tests auth, RBAC, CRUD endpoints, and tenant isolation at the API level.

```powershell
cd database
$env:PYTHONPATH="backend"
.\.venv\Scripts\pytest.exe backend/tests/ -v
```

### 3. Live OSV Integration Test (requires internet access)

**Path:** `database/tests/integration/`
**Purpose:** Verifies real vulnerability intelligence fetching from the live OSV API. This is isolated from the normal test suites to ensure deterministic offline builds.

```powershell
cd database
$env:PYTHONPATH="backend"
.\.venv\Scripts\pytest.exe -v tests/integration/test_e2e_osv.py
```

> **Note:** Do not use `testpaths = tests backend/tests` in `pytest.ini` for global discovery, as it triggers `import file mismatch` errors due to duplicate module basenames. Always run the suites explicitly as shown above, or use the `verify.ps1` script to run both sequentially.

### Tests that pass without PostgreSQL

A small subset of API tests (JWT signature validation, error format, validation handling) pass without a live database. All others require PostgreSQL.

---

## Database Verification

Connect to PostgreSQL and verify:

```sql
SELECT current_database();       -- Expected: dependencyhub
SELECT count(*) FROM information_schema.tables
  WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'; -- Expected: 24
SELECT version_num FROM alembic_version; -- Expected: b1ae584b89a0
```

---

## Current Supported Manifest Formats

| Format | File | Ecosystem |
|--------|------|-----------|
| npm | `package.json` | Node.js |

> **Note**: Additional manifest formats (requirements.txt, go.mod, Gemfile, pom.xml) are planned for future phases.

---

## Current Features

| Feature | Status |
|---------|--------|
| Multi-tenant organisation isolation | ✅ Live |
| JWT authentication + refresh tokens | ✅ Live |
| RBAC (Owner / Admin / Developer / Viewer) | ✅ Live |
| Repository (project) management | ✅ Live |
| Manifest upload + artifact storage | ✅ Live |
| Dependency parsing and persistence | ✅ Live |
| Vulnerability matching (fixture data) | ✅ Live |
| Dashboard summary and health score | ✅ Live |
| Dependency graph | ✅ Live |
| Vulnerability explorer | ✅ Live |
| Scanner UI (fixture-based simulation) | ✅ Live |
| Envelope encryption for artifacts | ✅ Live |
| Append-only audit log | ✅ Live |

---

## Known Limitations

- **Scanner uses OSV data** - The scanner uses real OSV-backed vulnerability intelligence to analyze your dependencies.
- **Outdated detection is not implemented** — Latest version comparison requires npm/PyPI registry integration (future scope).
- **Transitive dependency resolution is not implemented** — Only direct manifest dependencies are parsed.
- **GitHub integration is not implemented** — Repository sync requires a GitHub App (future scope).
- **Reports and audit-logs pages show fixture data** — These features are not yet backed by real API endpoints.
- **System health page shows fixture metrics** — Not connected to real infrastructure monitoring.

---

## Security Notes

- JWT access tokens expire after 30 minutes; refresh tokens after 7 days.
- Refresh tokens are stored as bcrypt hashes — raw tokens are never persisted.
- Artifact content is envelope-encrypted with per-artifact DEKs.
- The audit log is append-only and covers all security-sensitive operations.
- Tenant isolation is enforced at the repository layer — no cross-organisation data leakage.

---

## Future Roadmap

### P0 — Vulnerability Intelligence
- Real OSV / NVD provider integration
- Background scan worker
- Real-time scan events (SSE)

### P1 — Registry Intelligence
- npm and PyPI latest-version lookups
- Outdated package detection
- GitHub App and webhook integration
- Lockfile and transitive dependency resolution

### P2 — Remediation and Reporting
- Automated remediation recommendations
- Export-grade audit reports
- Email and webhook notifications
- Health scoring model

### P3 — Enterprise
- CI/CD security gates
- SAML/SSO
- Enterprise integrations
- Horizontal scaling

---

## Scripts

```powershell
# First-time setup
.\scripts\setup.ps1

# Start all services
.\scripts\start.ps1

# Stop services (no data loss)
.\scripts\stop.ps1

# Verify health and run tests
.\scripts\verify.ps1
```
