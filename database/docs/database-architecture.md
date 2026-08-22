# Dependency Hub — Database Architecture

## 1. Executive Summary

Dependency Hub is a multi-tenant software dependency health, license compliance, and vulnerability monitoring platform. The database architecture is built on PostgreSQL 16+ using SQLAlchemy 2.x and Alembic to guarantee schema versioning, tenant isolation, and cryptographic integrity.

```text
Developer / CI / Services
        ↓
Dependency Hub Platform Core
        ↓
SQLAlchemy 2.x (Asyncpg)
        ↓
PostgreSQL 16 Multi-Tenant Schema
```

---

## 2. Core Entity Hierarchy & Domain Model

```text
Organization (Primary Tenant Boundary)
  ├── Organization Members (Users + RBAC Roles + Permissions)
  ├── Security Policies (JSONB Compliance Rule Sets)
  ├── Audit Logs (Append-Only Lifecycle Events)
  └── Projects (Analyzed Repositories)
        ├── Project Artifacts (Immutable Code/Manifest Snapshots)
        │     ├── Envelope Encryption Metadata (IV, Tag, Encrypted DEK)
        │     └── Analysis Workspaces (Ephemeral Execution Sandboxes)
        ├── Scans (Reproducible Static & Dependency Analysis)
        │     ├── Dependencies (Direct & Transitive Packages)
        │     │     ├── Dependency Edges (Graph Topology & Depth)
        │     │     ├── Dependency Licenses (Detected Expressions)
        │     │     └── Dependency Versions (Freshness Intelligence)
        │     └── Dependency Vulnerabilities (Scan-Specific CVE Findings)
        └── Unified Findings (Aggregated Dashboard Reporting)
```

---

## 3. Database Entities & Tables

| Table Name | Entity | Primary Purpose |
| :--- | :--- | :--- |
| `organizations` | Organization | Primary tenant boundary with soft deletion support |
| `users` | User | Account identity, hashed passwords, verification state |
| `roles` | Role | System and custom roles (OWNER, ADMIN, DEVELOPER, etc.) |
| `permissions` | Permission | Granular atomic permissions (e.g. `scan.create`, `finding.update`) |
| `role_permissions` | Role-Permission | Many-to-many relationship mapping roles to permissions |
| `organization_members` | Membership | Links users to organizations under specific roles |
| `refresh_tokens` | Refresh Token | Hashed session tokens with revocation and expiry tracking |
| `projects` | Project | Organization codebases (repository URLs, visibility, language) |
| `project_artifacts` | Artifact | Immutable codebase snapshots (versioned, SHA-256 integrity) |
| `artifact_encryption_metadata`| Encryption Meta | Envelope encryption metadata (algorithm, IV, tag, encrypted DEK) |
| `analysis_workspaces` | Workspace | Ephemeral scan extraction and execution sandbox records |
| `scans` | Scan | Reproducible scan runs capturing scanner provenance & summary metrics |
| `package_ecosystems` | Ecosystem | Normalized package registries (npm, PyPI, Maven, Cargo, Go, etc.) |
| `dependencies` | Dependency | Extracted package dependencies per scan and ecosystem |
| `dependency_edges` | Dependency Graph| Directed dependency relationships with depth tracking |
| `vulnerabilities` | Vulnerability | Global CVE and security advisory repository |
| `dependency_vulnerabilities` | Findings Map | Scan-specific vulnerability findings on dependencies |
| `licenses` | License | Normalized SPDX license registry and risk levels |
| `dependency_licenses` | Dep License | License detections mapped to dependencies |
| `dependency_versions` | Dep Version | Version freshness and upgrade recommendations |
| `findings` | Unified Finding | Centralized triage entity for dashboard-level reporting |
| `security_policies` | Policy | JSONB rule engines for compliance and security gates |
| `audit_logs` | Audit Log | Append-only event history for security and compliance |

---

## 4. Multi-Tenancy Design

- **Primary Tenant Boundary**: All core resources (`projects`, `findings`, `policies`, `audit_logs`) are directly or transitively scoped to an `organization_id`.
- **Composite Uniqueness**: Project slugs (`organization_id`, `slug`) and memberships (`organization_id`, `user_id`) are scoped to the organization.
- **Tenant Isolation**: Queries filter on verified organization membership. Foreign keys prevent cross-tenant data leakage.

---

## 5. Artifact Security & Ephemeral Workspace Lifecycle

1. **Snapshot Ingestion**: An upload or repository sync creates a new `project_artifacts` row with an incremented `version_number` and SHA-256 `content_hash`.
2. **Immutability**: `is_immutable=True` guarantees snapshots are never overwritten in-place.
3. **Envelope Encryption**: Data Encryption Keys (DEKs) are generated and encrypted via external KMS (Vault/AWS/GCP KMS). Only ciphertext metadata is stored in `artifact_encryption_metadata`.
4. **Sandbox Isolation**: Scanners extract code into short-lived `analysis_workspaces` that auto-expire and are destroyed after analysis, preserving the untouched original artifact.

---

## 6. Indexing & Query Optimization Strategy

- **Tenant Scoping Indexes**: `idx_projects_org_status`, `idx_policies_org_active`, `idx_audit_org_created`, `idx_findings_org_severity_status`
- **Graph & Scan Traversal Indexes**: `idx_dependencies_scan_pkg`, `idx_dep_edges_parent_child`, `idx_scans_project_created`, `idx_scans_artifact_status`
- **Auth & Session Lookup**: `idx_users_email_active`, `idx_refresh_tokens_user_active`
