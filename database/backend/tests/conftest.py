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
