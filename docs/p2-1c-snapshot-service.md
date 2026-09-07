# P2.1C Canonical Immutable Report Snapshot Service

## 1. Objective
Build the internal Snapshot Service responsible for transforming a completed, persisted scan into a deterministic, tenant-safe, immutable ReportSnapshot.

## 2. Baseline & File Scope
* **Branch**: `feat/p2-report-intelligence`
* **P1 Release Commit**: `33b3146` (v1.2.0-p1-registry-intelligence)
* **Status**: **OBSERVED**

## 3. Source-of-Truth Matrix
* **Dependency & Registry Metadata**: Extracted purely from `Dependency.dependency_metadata["registry"]`. External provider calls (npm/PyPI/OSV) are strictly blocked.
* **Vulnerability Metadata**: Extracted strictly from `DependencyVulnerability.finding_metadata` and the global `Vulnerability` catalog.
* **Counts**:
  - `vulnerability_findings`: Absolute count of `DependencyVulnerability` rows for the scan.
  - `vulnerable_packages`: Distinct count of `dependency_id` in `DependencyVulnerability`.
* **Status**: **IMPLEMENTED**

## 4. Query Strategy
* **Approach**: Eager Loading via `selectinload` and `joinedload`.
* **Implementation**: The service uses `selectinload(Scan.dependencies)` and `selectinload(Scan.vulnerability_findings).joinedload(DependencyVulnerability.vulnerability)`.
* **Justification**: This prevents N+1 queries during the serialization loop and avoids Cartesian product explosion that would occur with a single giant `joinedload`.
* **Status**: **IMPLEMENTED**

## 5. Canonicalization & Serialization
* **Canonical Payload**: Separated completely from `metadata`. Contains only `project`, `scan`, `summary`, `dependencies`, and `vulnerabilities`.
* **Generation Metadata**: Includes volatile fields (`snapshot_id`, `created_at`, `snapshot_sha256`) and is kept outside the hash boundary.
* **Serialization Algorithm**:
  ```python
  json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
  ```
* **Status**: **IMPLEMENTED**

## 6. Hash Contract
* **Hash Algorithm**: SHA-256 over the UTF-8 encoded canonical JSON bytes.
* **Exclusion**: The hash strictly excludes its own `snapshot_sha256` value, memory pointers, and DB row IDs where irrelevant.
* **Reproducibility**: Identical source dependencies always produce identical hashes, regardless of DB return order (sorted in memory).
* **Status**: **IMPLEMENTED** & **TESTED**

## 7. Tenant Validation & Security
* **Tenant Validation**: The service asserts `report.organization_id == project.organization_id` and `report.project_id == scan.project_id`. Cross-tenant extraction raises `TenantMismatchError`.
* **Data Minimization**: Passwords, KMS DB references, HTTP logs, and raw exception tracebacks are actively excluded from the canonical payload.
* **Status**: **IMPLEMENTED** & **TESTED**

## 8. Idempotency & Concurrency
* **Idempotency**: Repeated calls to `create_snapshot()` for the same `report_id` return the existing snapshot.
* **Concurrency**: Handled via `db.begin_nested()` and catching `IntegrityError` on the DB's unique constraint (`ix_report_snapshots_report_id`). If lost, it safely recovers the winner's snapshot.
* **Transaction Ownership**: The service only uses `db.flush()`. It explicitly refuses to call `db.commit()`, preserving the outer transaction boundary for the caller.
* **Status**: **IMPLEMENTED** & **TESTED**

## 9. Immutability
* **Immutability**: Guaranteed at the service level. There is no `refresh_snapshot` or `update_snapshot` method.
* **Status**: **OBSERVED**

## 10. No-Live-Provider Proof
* **Verification**: Testing utilized `monkeypatch` to block `requests` and `httpx`. The snapshot service succeeds with 0 external network calls.
* **Status**: **TESTED**

## 11. Count Semantics & Edge Cases
* **1 vs 25**: Tested the exact "1 package / 25 findings" constraint. The service perfectly outputs `vulnerable_packages=1` and `vulnerability_findings=25`.
* **Empty Result**: A scan with zero findings successfully produces a valid canonical payload with `0` counts.
* **Status**: **TESTED**

## 12. Limitations & Deferred Work
* **Schema Validation**: Deep JSON schema validation (marshmallow/pydantic strictly for the JSON structure) is deferred. The dictionary construction acts as a strict programmatic schema.
* **API & Worker**: API endpoints and background processing are deferred to P2.1D.
* **Status**: **DEFERRED**
