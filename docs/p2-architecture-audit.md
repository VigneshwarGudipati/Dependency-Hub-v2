# Dependency Hub — P2.0 Architecture Audit (Verified against P1 Source)

## 1. Existing Reporting Forensics

A complete codebase sweep was performed to identify existing report-related architecture.

**Findings:**
* **Reports Page (`frontend/src/routes/_shell.reports.tsx`)**: OBSERVED (MOCK / DEFERRED). Renders an `EmptyState`.
* **Report Routes (Backend API)**: MISSING. No endpoints exist under `app/api/v1`.
* **Report Components**: MISSING.
* **Report API / Schemas**: MISSING.
* **Data Models**: OBSERVED. `Dependency`, `Scan`, `Project`, and `Vulnerability` are authoritative.
* **Deferred Models**: `DependencyVersion` and `Scan.outdated_dependencies`/`Scan.license_issues` are defined but NEVER written to by the P1 backend engine (`scan_worker.py`).
* **Artifact Storage**: OBSERVED. Project manifests use envelope encryption in PostgreSQL.
* **Authentication & RBAC**: OBSERVED. Standard tenant isolation present.
* **Download/Export Logic**: MISSING.

---

## 2. Source-of-Truth Matrix (Proven P1 Execution)

| Field | Exact DB path/model | Runtime writer | Runtime reader | API field | Truth classification |
|---|---|---|---|---|---|
| **installed_version** | `Dependency.package_version` | `ScanEngine.run` | `list_dependencies` | `installedVersion` | AUTHORITATIVE |
| **latest_version** | `Dependency.dependency_metadata["registry"]["latest_version"]` | `ScanEngine.run` | `list_dependencies` | `latestVersion` | PERSISTED REGISTRY METADATA |
| **outdated** | `Dependency.dependency_metadata["registry"]["outdated"]` | `ScanEngine.run` | `list_dependencies` | `outdated` | PERSISTED REGISTRY METADATA |
| **registry_source** | `Dependency.dependency_metadata["registry"]["provider"]` | `ScanEngine.run` | `list_dependencies` | `registrySource` | PERSISTED REGISTRY METADATA |
| **registry_status** | `Dependency.dependency_metadata["registry"]["status"]` | `ScanEngine.run` | `list_dependencies` | `registryStatus` | PERSISTED REGISTRY METADATA |
| **license** | `Dependency.dependency_metadata["registry"]["license"]` | `ScanEngine.run` | (Ignored by API currently) | `license` | PERSISTED REGISTRY METADATA |
| **published_at** | `Dependency.dependency_metadata["registry"]["published_at"]` | `ScanEngine.run` | `list_dependencies` | `publishedAt` | PERSISTED REGISTRY METADATA |
| **cache_state** | `Dependency.dependency_metadata["registry"]["cache_state"]` | `ScanEngine.run` | None | N/A | PERSISTED REGISTRY METADATA |
| **vulnerability** | `Vulnerability` | `VulnerabilityOrchestrator._persist_vulnerability` | `list_vulnerabilities` | `title` | AUTHORITATIVE |
| **severity** | `DependencyVulnerability.severity` | `VulnerabilityOrchestrator.match_vulnerabilities`| `list_vulnerabilities` | `severity` | AUTHORITATIVE |
| **advisory_id** | `Vulnerability.vulnerability_id` | `VulnerabilityOrchestrator._persist_vulnerability`| `list_vulnerabilities` | `cve` | AUTHORITATIVE |
| **affected_versions**| `DependencyVulnerability.finding_metadata["affected_versions"]`| `VulnerabilityOrchestrator.match_vulnerabilities`| `list_vulnerabilities` | `affectedVersions` | AUTHORITATIVE |

**Conclusion:** The `DependencyVersion` model is unused in P1. All registry intelligence is stored as JSON metadata inside `Dependency.dependency_metadata["registry"]`. All OSV specific metadata (affected/patched) is stored in `DependencyVulnerability.finding_metadata`.

---

## 3. P1 Integrity Check

* P1 baseline verified at tag `v1.2.0-p1-registry-intelligence` (Commit `33b3146`).
* No P1 core services were modified during this audit.
