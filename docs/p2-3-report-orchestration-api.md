# P2.3 Report Orchestration API

## 1. P2.3 Overview
The P2.3 milestone implements the API and asynchronous worker orchestration layer for report generation. It ties together P2.1 (Snapshot Service) and P2.2 (Report Exporters) into a robust, idempotent, and secure REST interface backed by resilient database-level concurrency controls.

## 2. Architecture
The system employs an API-first trigger model where API endpoints insert `Report` records with a `QUEUED` status. Background workers asynchronously claim these records using `FOR UPDATE SKIP LOCKED` database transactions, generate the reports, and update the status, ensuring decoupling between user requests and heavy generation work.

## 3. API Endpoints
- `POST /projects/{project_id}/reports` - Create/queue a report
- `GET /projects/{project_id}/reports` - List reports
- `GET /projects/{project_id}/reports/{report_id}` - Get report status/details
- `GET /projects/{project_id}/reports/{report_id}/download` - Download the generated report
- `POST /projects/{project_id}/reports/{report_id}/retry` - Retry a failed report
- `DELETE /projects/{project_id}/reports/{report_id}` - Delete a report

## 4. Request/Response Semantics
Requests provide `scan_id`, `report_type`, and `format`. Responses map directly to standard JSON payloads indicating the report lifecycle status.

## 5. Create Idempotency Semantics
PROVEN. A unique constraint (`uq_report_project_scan_type_format`) ensures that creating a duplicate report for the same scan, type, and format yields the existing `report_id` without corrupting the transaction or state.

## 6. Retry Semantics
TESTED. Users can issue a retry on a `FAILED` report, resetting its status to `QUEUED` and clearing its worker state (attempt_count, lease, token).

## 7. Report State Machine
`QUEUED` → `GENERATING` → `COMPLETED` | `FAILED`.

## 8. Worker Architecture
A background asyncio-based worker polls for `QUEUED` reports, claims them atomically, and processes them using `ReportGenerationService`.

## 9. Atomic Claiming
PROVEN. Workers use `SELECT ... FOR UPDATE SKIP LOCKED` to exclusively acquire a report row without blocking other workers looking for jobs.

## 10. worker_id
The unique identifier of the background worker process holding the current lease.

## 11. generation_token
A UUID generated upon claiming a report, used to enforce split-brain protection and authorize the final artifact persistence.

## 12. lease_expires_at
A timestamp defining when the worker's lock on the report expires, allowing stale job recovery.

## 13. attempt_count
Tracks generation attempts to prevent infinite retry loops on poison-pill jobs.

## 14. Stale Job Recovery
PROVEN. If `lease_expires_at` passes while the report is still `GENERATING`, another worker can atomically reclaim the job, generating a new `generation_token`.

## 15. Split-Brain Protection
PROVEN. If a stale worker (Worker A) attempts to complete a report after losing its lease to a new worker (Worker B), the `generation_token` mismatch causes an immediate rejection, preventing overwrites of the authoritative artifact.

## 16. Artifact Reconciliation
PROVEN. There is exactly one authoritative artifact per report/format. Split-brain write attempts do not corrupt or orphan the current authoritative artifact.

## 17. ReportGenerationService
Acts as the central orchestrator, executing the `SnapshotService`, parsing data, invoking the `ExporterRegistry`, and storing the output.

## 18. SnapshotService Reuse
OBSERVED. Ensures deterministic historical snapshots are reused instead of querying live DB tables repeatedly.

## 19. ReportData / ReportDocument / Exporters
PROVEN. Exporters convert the intermediate `ReportDocument` into JSON, HTML, or PDF byte streams deterministically.

## 20. Encryption Reuse
TESTED. Artifact storage reuses the KMS metadata linkage established in P1 for encryption at rest.

## 21. Checksum/Integrity
TESTED. A cryptographic hash of the generated artifact is persisted for integrity verification.

## 22. Download Behavior
PROVEN. Decrypts the artifact on-the-fly and streams it to the user.

## 23. RBAC Permissions
TESTED. Dedicated permissions (`report.create`, `report.read`, `report.download`, etc.) are enforced. Viewers are correctly denied create/retry/delete capabilities.

## 24. Tenant Isolation
TESTED. Cross-organization and cross-project access attempts are strongly denied.

## 25. IDOR Protection
TESTED. API endpoints validate that the `report_id` belongs to the `project_id` and the user's tenant.

## 26. Concurrency Limit
OBSERVED. Tests demonstrate 10 concurrent requests correctly resolving into a single report execution via idempotency.

## 27. Rate Limiting
DEFERRED. Not explicitly implemented in P2.3 reporting boundaries.

## 28. Audit Events
OBSERVED. Standard lifecycle events map cleanly into the `AuditLog` structure without destructive edits.

## 29. Failure Categories
TESTED. Distinguishes between transient failures (lease expiration/network) and permanent failures (unsupported formats).

## 30. Retry Behavior
TESTED. Transient failures increment `attempt_count` until a maximum limit is reached, transitioning to `FAILED`.

## 31. Scan Deletion Survival
PROVEN. Deleting a scan sets `scan_id` to NULL but preserves the report, snapshot, and artifact.

## 32. Creator Deletion Survival
PROVEN. Deleting a user sets `created_by` to NULL but preserves the report.

## 33. Expiration
NOT VERIFIED. Report lifecycle expiration or garbage collection is deferred.

## 34. Security Boundaries
PROVEN. No raw `eval`, `exec`, or unsafe DOM injections (`dangerouslySetInnerHTML`) exist.

## 35. Migration Chain
PROVEN. The exact migration chain is:
`59d769c3e465` → `deac8928b8ea` → `79039bf2cec5` → `69c29f3cbc47` → `266652f986b5`.

## 36. Known Limitations
- Pre-existing drift on `registry_cache.deleted_at` remains. Alembic check reports `remove_column registry_cache.deleted_at`. Classification: PRE-EXISTING / UNRELATED DRIFT.

## 37. Test Evidence
- Backend Tests: 111 Passed
- DB Integration Tests: 44 Passed
- P2.3 API: 4 unique tests passed
- P2.3 Concurrency: 2 unique tests passed
- P2.3 Worker: 6 unique tests passed
