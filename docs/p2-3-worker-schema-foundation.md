# P2.3 Worker Schema Foundation

## Problem
The P2.3 Report generation worker requires database-backed durability to safely generate reports in a decoupled background process. Specifically, the worker must safely claim generation tasks, recover from stale states, prevent infinite retry loops, and strictly prevent split-brain scenarios where two workers attempt to complete the same report generation simultaneously. The existing `Report` model lacked fields to support a robust job execution lifecycle.

## Required Invariants
1. **Durable Claiming**: A worker must claim a queued report safely via `FOR UPDATE SKIP LOCKED`.
2. **Attempt Limiting**: A single report must not be retried infinitely if it encounters fatal errors during generation.
3. **Split-Brain Protection**: If a worker's lease expires and another worker claims the report, the original worker must not be allowed to persist its result.
4. **Stale Recovery**: A worker must be able to reclaim a `GENERATING` report if the lease has expired and maximum attempts are not exhausted.

## Field Semantics
- `generation_started_at`: The timestamp when the current (or most recent) worker lease was established. NULL if the report has never been claimed.
- `error_category`: A predefined, safe string indicating the categorical reason for failure (e.g., "JOB_TIMEOUT", "PDF_RENDER_FAILED"). Prevents leaking traceback details.
- `attempt_count`: Integer counting the number of times this report has been claimed by a worker. Incrementing occurs atomically on claim.
- `worker_id`: The identifier of the worker that currently holds the lease for this report.
- `lease_expires_at`: The timestamp after which the report is considered stale and can be reclaimed by another worker.
- `generation_token`: A unique UUID generated upon every successful claim, acting as the definitive token for split-brain protection during completion.

## Claim Semantics
When claiming a `QUEUED` report, the worker will:
1. Issue a `SELECT ... FOR UPDATE SKIP LOCKED` query.
2. If successful, set `status = GENERATING`.
3. Increment `attempt_count`.
4. Set `generation_started_at = NOW()`.
5. Set `worker_id` and generate a new `generation_token`.
6. Set `lease_expires_at = NOW() + LEASE_DURATION`.

## Lease and Stale Recovery Semantics
- **Lease Expiration**: A lease expires when `NOW() > lease_expires_at`.
- **Stale Recovery**: A background sweeper or claiming worker can search for reports where `status = GENERATING` and `lease_expires_at < NOW()`.
- Upon recovery, if `attempt_count < MAX_ATTEMPTS`, the worker can reclaim it (using `FOR UPDATE SKIP LOCKED`), bump `attempt_count`, generate a NEW `generation_token`, and extend `lease_expires_at`.

## Split-Brain Protection
The unique `generation_token` ensures that only the worker holding the *current* lease can mark the report as `COMPLETED`.
If Worker A's lease expires and Worker B reclaims the job, Worker B gets a new `generation_token`. When Worker A later attempts to finish the job, its conditional update (`UPDATE ... WHERE id = X AND generation_token = TOKEN_A`) will fail, preventing Worker A from overwriting Worker B's result.

## Attempt Semantics
Each claim increments `attempt_count` atomically within the claim transaction.
If a worker crashes immediately after claiming, the attempt is permanently recorded.
**Maximum attempts** is set by the worker logic (e.g., 3). If `attempt_count >= MAX_ATTEMPTS` during stale recovery, the report is transitioned to `FAILED` with `error_category = 'JOB_TIMEOUT'`, preventing infinite crash loops.

## Migration and Existing Rows
A new Alembic migration (`79039bf2cec5_add_report_generation_lifecycle.py`) was generated to add these new columns.
- Before running the migration, we verified that there were **0 existing rows** in the `reports` table.
- Since the table was empty, we introduced the `attempt_count` column as `NOT NULL` with a default of `0` safely without requiring a complex backfill or data fabrication.
- P1 and P2.1B logic remain completely untouched and historical migrations were not modified.

## Testing Strategy
- Tests were added in `tests/integration/test_reports.py` to ensure schema constraints and field semantics behave properly.
- **Concurrent Claiming and Split-Brain Protection** tests validate that conditional updates enforcing `generation_token` block duplicate completions.
- The `format` column (added in P2.3 Schema Remediation) continues to enforce idempotency on generation requests via `uq_report_project_scan_type_format`.

## Remaining P2.3 Implementation Work
With the durable schema invariants in place, the system is now ready for:
1. The **Report API Endpoint** (`POST /api/v1/projects/{project_id}/reports`), which will idempotently create `Report` records.
2. The **Durable Background Worker** (`app.workers.report_worker`), which will pull from the database using these semantic rules and execute the `ReportGenerationService`.
