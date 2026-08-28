# Phase 1: Registry Intelligence Implementation Plan

## Architecture
The system will introduce a new `RegistryIntelligenceService` that implements a registry provider strategy pattern based on `RegistryProviderBase`.
When a scan occurs, the system fetches registry data (npm, PyPI) to enrich dependency information. A caching layer is used to prevent rate-limiting and accelerate repeated queries across projects.

- **RegistryProviderBase**: Abstract base class defining `get_package_metadata(name: str) -> RegistryMetadata`.
- **NpmRegistryProvider**: Implementation using `https://registry.npmjs.org/`.
- **PyPIRegistryProvider**: Implementation using `https://pypi.org/pypi/{name}/json`.

## Provider Interfaces
```python
class RegistryMetadata(BaseModel):
    name: str
    latest_version: Optional[str]
    description: Optional[str]
    license: Optional[str]
    homepage: Optional[str]
    repository: Optional[str]
    is_deprecated: bool
    deprecation_reason: Optional[str]
    published_at: Optional[datetime]
    maintainers_count: Optional[int]

class RegistryProviderBase(ABC):
    @abstractmethod
    async def get_package_metadata(self, package_name: str) -> RegistryMetadata:
        pass
```

## npm API
- **Endpoint**: `GET https://registry.npmjs.org/{package_name}`
- **Authentication**: None required.
- **Fields extracted**: `dist-tags.latest`, `description`, `license`, `homepage`, `repository.url`, `time[latest]`, `maintainers`.
- **Deprecation**: Checking `versions[latest].deprecated`.

## PyPI API
- **Endpoint**: `GET https://pypi.org/pypi/{package_name}/json`
- **Authentication**: None required.
- **Fields extracted**: `info.version` (latest), `info.summary`, `info.license`, `info.home_page`, `info.project_urls.Source` (or similar).

## Version Semantics & Outdated Detection
- Provide proper ecosystem-aware semantic version comparisons.
- **npm**: Uses standard semver comparison.
- **PyPI**: Uses PEP-440 rules.
- **Outdated Logic**: Compute if `installed_version` is strictly less than `latest_version`. If `installed_version` is an unresolved constraint (e.g. `^1.0.0`), do not attempt to guess an outdated status; leave as unresolved.

## Cache
- **Table**: `registry_cache` to store normalized metadata per package/ecosystem.
- **Key**: `ecosystem` + `package_name`.
- **TTL**: 24 hours.
- Includes: `fetched_at` and `expires_at`.

## Failure Semantics
- **HTTP 404 (Not Found)**: Metadata missing / No latest version available.
- **HTTP 429 / 5xx / Timeouts**: Map to `PROVIDER_UNAVAILABLE`. Use cached data if available (even if slightly stale, as a labeled fallback), else report `LATEST_UNKNOWN`.
- Never silently convert failures into "0 vulnerabilities" or "Up to date".

## DB Plan
- Add minimal Alembic migration to create the `registry_cache` table.
- Modify `dependency_metadata` in the `dependencies` table to store enriched registry information during scans.

## API Plan
- Enhance `GET /api/v1/dependencies/{id}` and dependency list to populate `installedVersion`, `latestVersion`, `outdated` status, `lastPublished`, `maintainers`, and `size`/`license` dynamically from the database using real data from the registry cache.

## Frontend Plan
- Replace static or mock UI strings on `_shell.packages.$packageId.tsx` with dynamic properties from the API.
- Properly reflect `Registry Unavailable` or `Latest version unknown` in the UI on provider failure.

## Tests
- Mock HTTPX in Pytest for deterministic tests of NPM/PyPI parsing and mapping.
- Add live integration tests against real NPM (`react`) and PyPI (`requests`) endpoints.
- Test failure handling, timeouts, and cache behavior.

## Security
- Enforce strict connect/read/overall timeouts (e.g., 10 seconds).
- Do not execute or `eval()` incoming version strings.
- Process and discard untrusted JSON fields; store only validated data structure.

## Rollout Plan
1. Create DB Migration for `registry_cache`.
2. Implement abstract and concrete Registry Providers.
3. Implement `RegistryIntelligenceService` with caching.
4. Integrate with `ScanWorker` to enrich `dependency_metadata`.
5. Expose fields via `DependencyService` API layer.
6. Verify Frontend rendering with live backend data.
7. Perform Phase Gate verification.
