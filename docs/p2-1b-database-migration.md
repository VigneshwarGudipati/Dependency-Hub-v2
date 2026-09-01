# P2.1B Database Migration & Schema Validation

## 1. Baseline
* **Branch**: `feat/p2-report-intelligence`
* **P1 Release Commit**: `33b3146` (v1.2.0-p1-registry-intelligence)
* **Status**: **OBSERVED**

## 2. Alembic Migration Forensics & Generation
* **Revision**: `59d769c3e465` (Revises: `e2f3g4h5i6j7`)
* **Tables Created**: `reports`, `report_snapshots`, `report_artifacts`, `report_encryption_metadata`
* **Status**: **IMPLEMENTED**

## 3. Columns & Types Verification
* `Report.scan_id`: UUID, `nullable=True`
* `Report.created_by`: UUID, `nullable=True`
* `ReportSnapshot.snapshot_data`: JSONB
* `ReportArtifact.encrypted_data`: BYTEA
* `ReportArtifact.format`: ENUM
* **Status**: **VERIFIED**

## 4. Foreign Key Constraints & ON DELETE
* **Report -> Organization**: `RESTRICT`
* **Report -> Project**: `CASCADE`
* **Report -> Scan**: `SET NULL`
* **Report -> User**: `SET NULL`
* **ReportArtifact -> Report**: `CASCADE`
* **ReportSnapshot -> Report**: `CASCADE`
* **ReportEncryptionMetadata -> ReportArtifact**: `CASCADE`
* **Status**: **IMPLEMENTED** & **TESTED**

## 5. Enum Strategy
* **Approach**: Native Enum = `False` (`VARCHAR`-backed SQLAlchemy enum).
* **Consistency**: Matches exactly how P1 handled `license_category_enum`, `severity_level_enum`, etc., in `0001_initial_database_schema.py`.
* **Status**: **IMPLEMENTED**

## 6. Index Strategy
* Non-PK indexes created:
  - `ix_reports_organization_id`
  - `ix_reports_project_id`
  - `ix_reports_scan_id`
  - `ix_reports_status`
  - `ix_report_artifacts_report_id`
  - `ix_report_snapshots_report_id` (Unique acting as 1:1 constraint)
  - `ix_report_encryption_metadata_artifact_id` (Unique acting as 1:1 constraint)
* **Justification**: These indexes directly support the access patterns required by the reporting architecture (filtering by tenant, project, source scan, status).
* **Status**: **IMPLEMENTED**

## 7. Migration Operations
* **Upgrade Test**: Executed `alembic upgrade head`. Schema applied successfully.
* **Downgrade Test**: Executed `alembic downgrade -1`. Tables dropped cleanly in local DB.
* **Round-Trip Test**: Re-executed `alembic upgrade head`. Tables restored perfectly.
* **Status**: **TESTED**

## 8. Database Integration Test Results
* Integration tests executed successfully against the local PostgreSQL container.
* Verified schema aspects:
  - Tables and Columns exist natively
  - FK constraints enforce relational bounds
  - `ON DELETE SET NULL` preserves reports after scan/user deletion
  - One-to-one snapshot constraint works via Unique Index
  - Artifact format uniqueness works via Composite Unique Constraint
* **Status**: **TESTED**

## 9. P1 Regression Results
* Executed full regression suite (`backend/tests` and `database/tests`)
* **Total Tests Passed**: 132 (including existing P1 tests)
* **Status**: **TESTED**

## 10. Tenant Consistency & Snapshot Immutability (Architecture Notes)
* **Tenant Consistency**: The invariant `Report.organization_id == Project.organization_id` is **SERVICE-ENFORCED**. The database schema does not feature a composite FK bridging both tables simultaneously to prevent cross-tenant writes natively.
* **Snapshot Immutability**: Immutability is **SERVICE-ENFORCED**. The database table does not feature an `UPDATE`-blocking trigger (avoiding arbitrary triggers per rules).
* **Status**: **OBSERVED**

## 11. Schema Diff Validation
* Compared ORM metadata vs actual PostgreSQL schema via second autogenerate pass.
* **Findings**: The only detected drift was an unrelated `registry_cache.deleted_at` removal proposed by Alembic, which was stripped manually from the generated migration to adhere strictly to the "DO NOT create unrelated schema changes" rule. The P2 tables matched exactly.
* **Status**: **OBSERVED**

## 12. Final File Scope
* **Allowed Additions**: Only the single new Alembic revision `59d769c3e465_add_report_intelligence_tables.py`, test file `test_reports.py`, and documentation artifacts.
* **Status**: **VERIFIED**

## 13. Remaining P2 Work (Deferred)
* Report Workers (Queue polling)
* Exporters (PDF, HTML, SARIF)
* API endpoints
* **Status**: **DEFERRED**
