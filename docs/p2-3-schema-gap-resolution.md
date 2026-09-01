# Dependency Hub P2.3 Schema Gap Resolution

## Overview
During the transition to the Phase 2.3 Report Orchestration and durability worker models, a critical schema gap was identified that compromised both idempotency and proper format tracking:

1. `Report.format` was missing, forcing the system to derive the intended format through post-facto inference via `ReportArtifact.format`.
2. Report generation idempotency (duplicate prevention) could only be evaluated by inspecting completed artifacts, creating race conditions during concurrent worker generation for the same requested report.

This schema gap remediation enforces these properties at the database level.

## Schema Modifications

### `Report.format` Field
Added the `format` column directly to the `reports` table to capture the intended output format at the time the request is queued.

```python
format: Mapped[ReportFormat] = mapped_column(Enum(ReportFormat), nullable=False)
```

By making this field `nullable=False`, we ensure the queue cannot accept ambiguous generation requests.

### Composite Idempotency Constraint
Added a composite `UniqueConstraint` on the `reports` table.

```python
__table_args__ = (
    UniqueConstraint(
        "project_id",
        "scan_id",
        "report_type",
        "format",
        name="uq_report_project_scan_type_format",
    ),
)
```

**Lifecycle Constraint Analysis:**
- Historical reports survive deletion of their source scan via `scan_id` being `nullable=True`.
- The database enforces uniqueness for NEW generation requests where `scan_id` is specified.
- The `IntegrityError` raised by PostgreSQL naturally prevents redundant enqueues in a safe, concurrent manner without application-level distributed locks.

## Migration Details
The Alembic migration `deac8928b8ea_add_report_generation_intent.py` introduces these changes.
Drift related to caching and audit logs detected in the environment was excluded to maintain a focused migration scope.

## Test Validation
Extensive integration tests were developed in `test_reports.py` to assert:
- `Report.format` durability and persistence across reload.
- Strict enforcement of duplicate rejection (`IntegrityError` raised for identical configurations).
- Allowance of orthogonal configurations (different format, different scan, different project, etc.).
- Full preservation of existing behavior via regression suite (111 tests).

The baseline durability layer is now complete and verified.
