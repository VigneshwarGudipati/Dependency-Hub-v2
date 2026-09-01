# P2.2 ReportData & Exporter Foundation

## 1. Overview
This document serves as the architectural and security blueprint for the P2.2 epic, encompassing `ReportData`, `ReportDocument`, and the three core exporters (`JSON`, `HTML`, `PDF`).

## 2. Baseline & Context
- **Baseline**: `v1.2.0-p1-registry-intelligence` (`33b3146`)
- **P2.1C Snapshot Service**: The source of truth. Snapshots provide canonical, deterministic payloads containing vulnerability and registry facts.
- **Architectural Boundary**: Exporters strictly consume `ReportDocument`. They never query live databases and never make external HTTP requests.

## 3. ReportData Structure (OBSERVED/IMPLEMENTED)
`ReportData` is the normalized representation of business facts extracted safely from `ReportSnapshot.snapshot_data["canonical_payload"]`.
- Enforces strict Pydantic parsing.
- Ensures `outdated_packages` and `unknown_packages` counts are explicitly derived rather than guessed.
- Exposes clean access to `registry_metadata` and `finding_metadata`.
- Maintains 1 package / 25 findings semantics without tampering (TESTED).

## 4. ReportDocument Structure (IMPLEMENTED)
`ReportDocument` translates pure business facts into layout primitives suitable for rendering:
- `ReportDocumentMetadata`
- `GenericSection`
- `MetricCard`
- `DataTable`
- This ensures JSON, HTML, and PDF all exhibit exact semantic consistency (TESTED).

## 4.1 JSON Public Contract & Hash Semantics (IMPLEMENTED)
The JSON exporter provides the following exact top-level structure (v1.0.0):
```json
{
  "metadata": {
    "report_id": "uuid",
    "scan_id": "uuid",
    "snapshot_sha256": "hash",
    "generator_version": "1.0.0",
    "document_schema_version": "1.0.0",
    "created_at": "iso8601"
  },
  "project_name": "string",
  "sections": [
    {
      "title": "string",
      "content": "string",
      "metrics": [{"label": "string", "value": "string", "severity_class": "string|null"}],
      "tables": [{"headers": ["string"], "rows": [{"cells": {"key": "value"}}]}]
    }
  ]
}
```
**JSON Hash Terminology**: `snapshot_sha256` = canonical snapshot payload integrity hash. It is explicitly NOT the checksum of the exported JSON file itself.

## 5. Exporter Architecture (IMPLEMENTED)
- **JSON Exporter**: Dumps `ReportDocument` natively to `UTF-8` with `ensure_ascii=False` and strict key sorting.
- **HTML Exporter**: Uses **Jinja2** template rendering. Applies auto-escaping to all inputs to prevent XSS. Embeds a strict CSP: `default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:`.
- **PDF Exporter**: Uses **xhtml2pdf** to convert the safe HTML output into a PDF document.

## 6. Dependency Governance (IMPLEMENTED)
Two minimal-footprint dependencies were introduced:
- `jinja2>=3.1.4`: Chosen for standard HTML XSS auto-escaping.
- `xhtml2pdf>=0.2.16`: Chosen for pure-Python HTML-to-PDF rendering (avoids Chromium footprints and native GTK/Cairo compilation errors on Windows).

## 7. Security Model (TESTED)
- **XSS Mitigation**: Jinja2 ensures `<script>alert('XSS')</script>` is cleanly escaped as text.
- **SSRF / Local File Disclosure**: The PDF renderer uses a resource-access restriction callback that universally rejects all dynamic external resource fetching (`http://`, `file://`), preventing injection.
- **Network Isolation**: Verified using `monkeypatch` to block `httpx` and `requests`. Zero external calls occur during report generation.
- **Database Isolation**: Verified using SQLAlchemy `after_cursor_execute` event listeners. Zero database queries execute after the snapshot is passed into the `ReportData` pipeline.

## 8. Unicode & Accessibility
- **JSON Unicode**: TESTED (`ensure_ascii=False` applied).
- **HTML Unicode**: TESTED (UTF-8 encoding natively handled).
- **PDF Unicode**: PARTIAL (Accented Latin renders natively. Hindi, Tamil, Arabic, CJK, and Emoji fallback to tofu blocks `■` since pure `xhtml2pdf` lacks native font glyphs without explicitly providing TTF fonts).
- **Accessibility**: NOT VERIFIED (HTML supports semantic tags natively, but `xhtml2pdf` doesn't emit native tagged PDFs (PDF/UA)).

## 9. Performance & Pagination (TESTED)
- HTML and PDF generators rely on CSS `page-break-inside: avoid;` to keep table rows structured without silent truncation.
- Scalability to 1,000+ dependencies works natively within Memory limits without unbounded recursion, constrained mainly by the `ReportData` Pydantic payload footprint. Tested via explicit 1,000 dependency load test without omitting or duplicating rows.

## 10. Filename Safety (TESTED)
`generate_safe_filename` restricts inputs to `[A-Za-z0-9_-]`, prevents path traversal (`../`), handles reserved Windows system names (`CON`, `PRN`), and safely truncates.

## 11. Artifact Boundary (IMPLEMENTED)
Exporters return raw bytes. They explicitly **do not** interact with `ProjectArtifact` persistence or AWS/S3 uploads, keeping the core pipeline free of I/O boundaries.

## 12. SnapshotService Repair Classification (P2.1C FIX)
- **P1 RELEASED CODE MODIFIED**: NO
- **P2.1C CODE MODIFIED**: YES
- **Original defect:** `SnapshotService` used synchronous SQLAlchemy calls (`.query()`, `with db.begin_nested()`) on an `AsyncSession`, causing `AttributeError` and total test suite failure during integration.
- **Why P2.2 exposed it:** P2.2 tests run the full end-to-end extraction from a real `AsyncSession` to mimic production endpoints.
- **Exact fix:** Refactored `SnapshotService` to properly await async statements: `await db.execute(select(...))` and `async with db.begin_nested()`.
- **Why required:** Without this fix, the P2.2 end-to-end tests fundamentally crash before P2.2 code executes.
- **Regression:** P1 is entirely unmodified (0 changes). P2.1C was corrected to match the existing async connection semantics of the backend.

## 13. Exact Test Counts
- **focused reporting tests** = 10
- **snapshot tests** = 7
- **backend tests** = 111
- **database tests** = 15

## 14. PDF Security Classification
- **network access** = BLOCKED
- **local file access** = BLOCKED
- **process isolation** = NOT VERIFIED (Runs in-process via xhtml2pdf pure-python)
- **filesystem isolation** = NOT VERIFIED (No disk I/O occurs, outputs to BytesIO)

## 15. Cross-Format Validation & File Cleanup (TESTED)
- **Temp cleanup results:** `residual files = 0`. Exporters write entirely to in-memory `BytesIO` streams. Verified disk usage is isolated.
- **Concurrency results:** Due to pure memory/BytesIO generation, 10 concurrent requests yield 10 successful outputs with no lock contention or temp collisions. Verified explicitly via `asyncio.gather` execution.
- **Cross-Format:** JSON, HTML, and PDF share identical source structs (`ReportDocument`), maintaining parity on exact dependency and vulnerability counts. Verified by explicit cross-format structural assertions.

## 16. Known Limitations & Deferred Features
- PDF process isolation is lacking since it executes in the same Python runtime via `xhtml2pdf`. A true isolated process (e.g. headless chromium sandbox) is out of scope for P2.2 but may be evaluated later for higher PDF rendering fidelity.
- CSV Export (Deferred)
- SARIF Export (Deferred)
- Report HTTP API (Deferred)
- Report Worker (Deferred)
