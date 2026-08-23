# Special Pages Audit

## Overview
This document catalogs the current state of "special" or secondary pages in the Dependency Hub frontend.

| Page / Route | Current State | Action Required | Persistent Data? | API Endpoints | Resulting State |
|--------------|---------------|-----------------|------------------|---------------|-----------------|
| `/scanner` | MOCK | Convert to REAL pipeline | Yes (DB `ProjectScan`) | `POST /projects/{id}/artifacts`<br>`POST /projects/{id}/scans`<br>`GET /projects/{id}/scans/{scan_id}` | REAL |
| `/system-health` | MOCK (mockService) | Convert to REAL endpoints | No | `GET /health`<br>`GET /health/database`<br>`GET /ready` | REAL |
| `/users` | MOCK (mockData) | Convert to REAL endpoint | Yes (DB `OrganizationMember`) | `GET /members` | REAL |
| `/audit-logs` | MOCK (mockService) | Mark as DEFERRED | No (Not in current scope) | None | DEFERRED |
| `/reports` | MOCK (mockService) | Mark as DEFERRED | No (Not in current scope) | None | DEFERRED |
| `/notifications` | MOCK | Mark as DEFERRED | No (Not in current scope) | None | DEFERRED |
| `/settings/*` | MOCK / FAKE | Mark as DEFERRED / Explicit | No (Not in current scope) | None | DEFERRED |

## Mock Data vs Real Implementation

### Scanner
The standalone `/scanner` page currently uses `mockService.runScan` which fakes scan progress with `setTimeout` and doesn't interact with the backend. It will be rewritten to use the real artifact upload and asynchronous scan creation API. TanStack query will be used to poll the scan status and invalidate related cache entries upon completion. Messages like "resolve the tree against live advisory data" will be changed to truthful backend operations (e.g., "Parsing dependencies").

### Users / Members
The `/users` page currently uses `mockData`. We will wire it up to use `apiClient.get('/members')` which exists in the backend API.

### System Health
The `/system-health` page currently uses `mockService`. We will wire it up to fetch real metrics from `/health` and `/ready` endpoints of the FastAPI application.

### Audit Logs, Reports, Notifications, Settings
These pages currently load fake mock data. Since building out comprehensive PDF exports or notification hubs is out of the P0 scope, we will replace the mock data with a truthful "Deferred / Coming Soon" empty state in the UI.

### Branding & Identity
- "DepSentry" branding will be completely replaced with "Dependency Hub".
- The hardcoded user identity "Priya" will be replaced by an authenticated identity fetched from `/auth/me`.
- Suspicious defaults like "Jan 1, 1970" for "Never scanned" repositories will be fixed.
