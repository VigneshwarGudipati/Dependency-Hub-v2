import pytest
import pytest_asyncio
import httpx

class MockRegistryResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://test")
            raise httpx.HTTPStatusError("Error", request=request, response=httpx.Response(self.status_code, request=request))

@pytest_asyncio.fixture(scope="function", autouse=True)
async def mock_registry_httpx(monkeypatch):
    """Globally mock HTTPX so backend tests never hit real npm/PyPI."""
    npm_data = {
        "name": "mocked-pkg",
        "dist-tags": {"latest": "2.0.0"},
        "license": "MIT",
        "time": {"2.0.0": "2024-04-25T19:00:00Z"},
    }
    pypi_data = {
        "info": {"version": "2.0.0", "license": "MIT"},
        "releases": {"2.0.0": [{"upload_time_iso_8601": "2024-04-25T19:00:00Z"}]}
    }

    # Store the original get
    original_get = httpx.AsyncClient.get

    async def mock_get(self_or_client, url, *args, **kwargs):
        url_str = str(url)
        if "registry.npmjs.org" in url_str:
            return MockRegistryResponse(200, npm_data)
        elif "pypi.org" in url_str:
            return MockRegistryResponse(200, pypi_data)

        # fallback to original if not a registry call
        # e.g. OSV tests might hit OSV mock
        return await original_get(self_or_client, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

@pytest.fixture(autouse=True)
def cleanup_test_artifacts():
    """Ensure artifacts created during the test are removed."""
    from pathlib import Path
    from app.core.config import settings
    storage_dir = Path(settings.STORAGE_DIR)

    # Snapshot before test
    files_before = set()
    if storage_dir.exists():
        files_before = {f for f in storage_dir.rglob('*') if f.is_file()}

    yield

    # Cleanup after test
    if storage_dir.exists():
        files_after = {f for f in storage_dir.rglob('*') if f.is_file()}
        new_files = files_after - files_before
        for new_file in new_files:
            try:
                new_file.unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                # Cleanup failures must not be silently swallowed
                raise RuntimeError(f"Failed to cleanup test storage file {new_file}") from e
