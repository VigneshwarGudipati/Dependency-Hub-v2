# Dependency Hub — Standalone Database Foundation

> **Monitor. Analyze. Secure.**  
> Standalone PostgreSQL database architecture, SQLAlchemy 2.x ORM models, and Alembic migrations for the Dependency Hub multi-tenant software dependency health platform.

---

## Architecture Overview

```text
Developer / CI / Backend
           ↓
Docker Compose (PostgreSQL 16)
           ↓
SQLAlchemy 2.x (Asyncpg)
           ↓
Alembic Migrations
           ↓
Dependency Hub Database Schema
           ↓
Automated Test Suite (pytest)
```

---

## Quickstart Guide

### 1. Prerequisites

* **Docker & Docker Compose**
* **Python 3.12+** (tested on Python 3.14)

### 2. Start PostgreSQL via Docker

```bash
docker compose up -d
```

Verify container status:
```bash
docker compose ps
```

### 3. Setup Python Virtual Environment

```bash
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
# source .venv/bin/activate

pip install -r backend/requirements.txt
```

### 4. Configure Environment

Copy `.env.example` to `.env` if not already created:
```bash
cp .env.example .env
```

### 5. Run Database Migrations

Apply the complete baseline schema using Alembic:
```bash
# On Windows PowerShell:
$env:PYTHONPATH="backend"; alembic upgrade head

# On Linux/macOS:
PYTHONPATH=backend alembic upgrade head
```

### 6. Seed Reference Data

Seed initial system roles, permissions, package ecosystems, and standard licenses:
```bash
# On Windows PowerShell:
$env:PYTHONPATH="backend"; python backend/app/seed.py

# On Linux/macOS:
PYTHONPATH=backend python backend/app/seed.py
```

### 7. Run Automated Tests

Execute the comprehensive test suite:
```bash
pytest -v
```

---

## Project Structure

```text
DependencyHub-Database/
│
├── docker-compose.yml              # PostgreSQL 16 container definition
├── .env.example                    # Environment variable template
├── .gitignore                      # Git ignore configuration
├── pytest.ini                      # Pytest and asyncio configuration
├── alembic.ini                     # Alembic migration configuration
├── README.md                       # Project overview & documentation
│
├── backend/
│   ├── requirements.txt            # Pinned dependencies
│   └── app/
│       ├── __init__.py
│       ├── seed.py                 # CLI reference seeding tool
│       ├── verify_schema.py        # Database schema inspection script
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py           # Pydantic settings & database URLs
│       │   ├── database.py         # SQLAlchemy async engine & health check
│       │   └── seeds.py            # Idempotent reference data seeders
│       │
│       ├── models/
│       │   ├── __init__.py         # Central model exports
│       │   ├── base.py             # DeclarativeBase, UUID & Timestamp mixins
│       │   ├── user.py             # User account & credential entity
│       │   ├── organization.py     # Organization & membership entities
│       │   ├── role.py             # RBAC Role entity & system role enums
│       │   ├── permission.py       # Permissions & Role-Permission mappings
│       │   ├── project.py          # Project repositories & visibility
│       │   ├── artifact.py         # Immutable project snapshot artifacts
│       │   ├── encryption.py       # Envelope encryption metadata
│       │   ├── workspace.py        # Ephemeral analysis sandboxes
│       │   ├── scan.py             # Scan execution & provenance metrics
│       │   ├── ecosystem.py        # Package registry ecosystems (npm, PyPI, etc.)
│       │   ├── dependency.py       # Dependencies & directed dependency graph
│       │   ├── vulnerability.py    # Global CVE catalog & scan findings
│       │   ├── license.py          # Licenses, detections & version intelligence
│       │   ├── finding.py          # Unified findings for dashboard reporting
│       │   ├── policy.py           # Organization security policies (JSONB)
│       │   ├── audit.py            # Append-only security audit log
│       │   └── refresh_token.py    # Hashed refresh tokens
│       │
│       └── repositories/
│           └── __init__.py
│
├── alembic/
│   ├── env.py                      # Async migration runner
│   ├── script.py.mako              # Migration file template
│   └── versions/
│       └── b1ae584b89a0_0001_initial_database_schema.py
│
├── tests/
│   ├── conftest.py                 # Async fixtures & database isolation
│   ├── test_database.py            # Health check & connection tests
│   ├── test_relationships.py       # Entity persistence & ORM relationships
│   ├── test_constraints.py         # Uniqueness & foreign-key constraints
│   ├── test_artifacts.py           # Immutability & envelope encryption tests
│   └── test_multitenancy.py        # Tenant isolation & scoping tests
│
└── docs/
    ├── database-architecture.md    # Architecture & domain model specification
    ├── database-erd.md             # Mermaid ER Diagram
    └── security-model.md           # Security & cryptographic boundaries
```

---

## Schema Highlights

* **Multi-Tenant Foundation**: Complete isolation anchored on `organizations`.
* **Envelope Encryption**: Stored artifacts encrypted with DEKs; master keys remain in external KMS.
* **Immutable Artifacts**: Versioned snapshots prevent in-place code mutation.
* **Reproducible Scans**: Track scanner commit, ruleset version, vulnerability DB version, and exact artifact analyzed.
* **PostgreSQL Native Graph**: Relational directed graph (`dependency_edges`) with traversal indexes.
* **Security & Compliance**: Append-only `audit_logs`, hashed `refresh_tokens`, no plaintext secrets.
