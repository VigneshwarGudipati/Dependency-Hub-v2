import pytest
from datetime import datetime
import httpx
from unittest.mock import AsyncMock

from app.services.registry.base import RegistryStatus, OutdatedStatus
from app.services.registry.npm import NpmRegistryProvider

@pytest.fixture
def npm_provider():
    return NpmRegistryProvider()

class MockResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        if self._json_data == "MALFORMED":
            raise ValueError("Malformed JSON")
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://test")
            raise httpx.HTTPStatusError("Error", request=request, response=httpx.Response(self.status_code, request=request))

@pytest.mark.asyncio
async def test_npm_valid_package_metadata(npm_provider, monkeypatch):
    mock_data = {
        "name": "react",
        "dist-tags": {"latest": "18.3.1"},
        "license": "MIT",
        "time": {"18.3.1": "2024-04-25T19:00:00Z"},
        "repository": {"type": "git", "url": "git+https://github.com/facebook/react.git"}
    }

    async def mock_get(*args, **kwargs):
        return MockResponse(200, mock_data)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await npm_provider.get_package_metadata("react", installed_version="18.2.0")

    assert res.status == RegistryStatus.SUCCESS
    assert res.latest_version == "18.3.1"
    assert res.license == "MIT"
    assert res.outdated == OutdatedStatus.TRUE
    assert res.published_at.year == 2024
    assert res.source == "git+https://github.com/facebook/react.git"

@pytest.mark.asyncio
async def test_npm_installed_equals_latest(npm_provider, monkeypatch):
    mock_data = {"dist-tags": {"latest": "1.0.0"}}
    async def mock_get(*args, **kwargs): return MockResponse(200, mock_data)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await npm_provider.get_package_metadata("pkg", installed_version="1.0.0")
    assert res.outdated == OutdatedStatus.FALSE

@pytest.mark.asyncio
async def test_npm_invalid_installed_version(npm_provider, monkeypatch):
    mock_data = {"dist-tags": {"latest": "1.0.0"}}
    async def mock_get(*args, **kwargs): return MockResponse(200, mock_data)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    # constraint
    res = await npm_provider.get_package_metadata("pkg", installed_version="^1.0.0")
    assert res.outdated == OutdatedStatus.UNKNOWN

    # latest keyword
    res2 = await npm_provider.get_package_metadata("pkg", installed_version="latest")
    assert res2.outdated == OutdatedStatus.UNKNOWN

    # wildcard / x-ranges
    res3 = await npm_provider.get_package_metadata("pkg", installed_version="1.x")
    assert res3.outdated == OutdatedStatus.UNKNOWN

    res4 = await npm_provider.get_package_metadata("pkg", installed_version="1.0.*")
    assert res4.outdated == OutdatedStatus.UNKNOWN

    res5 = await npm_provider.get_package_metadata("pkg", installed_version="*")
    assert res5.outdated == OutdatedStatus.UNKNOWN

@pytest.mark.asyncio
async def test_npm_prerelease_versions(npm_provider, monkeypatch):
    mock_data = {"dist-tags": {"latest": "1.0.0"}}
    async def mock_get(*args, **kwargs): return MockResponse(200, mock_data)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    # valid concrete prerelease
    res = await npm_provider.get_package_metadata("pkg", installed_version="1.0.0-alpha.1")
    assert res.outdated == OutdatedStatus.TRUE

    # valid concrete version with build metadata
    res2 = await npm_provider.get_package_metadata("pkg", installed_version="1.0.0+build.123")
    assert res2.outdated == OutdatedStatus.FALSE

@pytest.mark.asyncio
async def test_npm_package_not_found(npm_provider, monkeypatch):
    async def mock_get(*args, **kwargs): return MockResponse(404)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await npm_provider.get_package_metadata("pkg", installed_version="1.0.0")
    assert res.status == RegistryStatus.NOT_FOUND
    assert res.outdated == OutdatedStatus.UNKNOWN

@pytest.mark.asyncio
async def test_npm_rate_limited(npm_provider, monkeypatch):
    async def mock_get(*args, **kwargs): return MockResponse(429)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await npm_provider.get_package_metadata("pkg")
    assert res.status == RegistryStatus.RATE_LIMITED

@pytest.mark.asyncio
async def test_npm_provider_unavailable_500(npm_provider, monkeypatch):
    async def mock_get(*args, **kwargs): return MockResponse(500)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await npm_provider.get_package_metadata("pkg")
    assert res.status == RegistryStatus.PROVIDER_UNAVAILABLE

@pytest.mark.asyncio
async def test_npm_timeout(npm_provider, monkeypatch):
    async def mock_get(*args, **kwargs): raise httpx.TimeoutException("Timeout")
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await npm_provider.get_package_metadata("pkg")
    assert res.status == RegistryStatus.PROVIDER_UNAVAILABLE
    assert res.error_code == "TIMEOUT"

@pytest.mark.asyncio
async def test_npm_network_error(npm_provider, monkeypatch):
    async def mock_get(*args, **kwargs): raise httpx.RequestError("Network error")
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await npm_provider.get_package_metadata("pkg")
    assert res.status == RegistryStatus.PROVIDER_UNAVAILABLE
    assert res.error_code == "NETWORK_ERROR"

@pytest.mark.asyncio
async def test_npm_malformed_json(npm_provider, monkeypatch):
    async def mock_get(*args, **kwargs): return MockResponse(200, "MALFORMED")
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await npm_provider.get_package_metadata("pkg")
    assert res.status == RegistryStatus.INVALID_RESPONSE
    assert res.error_code == "MALFORMED_JSON"

from app.services.registry.pypi import PyPIRegistryProvider

@pytest.fixture
def pypi_provider():
    return PyPIRegistryProvider()

@pytest.mark.asyncio
async def test_pypi_valid_package_metadata(pypi_provider, monkeypatch):
    mock_data = {
        "info": {
            "version": "2.31.0",
            "license": "Apache 2.0",
            "home_page": "https://requests.readthedocs.io",
            "project_urls": {"Source": "https://github.com/psf/requests"}
        },
        "releases": {
            "2.31.0": [{"upload_time_iso_8601": "2023-05-22T16:16:03.111425Z"}]
        }
    }

    async def mock_get(*args, **kwargs): return MockResponse(200, mock_data)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await pypi_provider.get_package_metadata("requests", installed_version="2.30.0")

    assert res.status == RegistryStatus.SUCCESS
    assert res.latest_version == "2.31.0"
    assert res.license == "Apache 2.0"
    assert res.outdated == OutdatedStatus.TRUE
    assert res.published_at.year == 2023
    assert res.source == "https://github.com/psf/requests"

@pytest.mark.asyncio
async def test_pypi_installed_equals_latest(pypi_provider, monkeypatch):
    mock_data = {"info": {"version": "1.0.0"}}
    async def mock_get(*args, **kwargs): return MockResponse(200, mock_data)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await pypi_provider.get_package_metadata("pkg", installed_version="1.0.0")
    assert res.outdated == OutdatedStatus.FALSE

@pytest.mark.asyncio
async def test_pypi_prerelease_and_postrelease(pypi_provider, monkeypatch):
    mock_data = {"info": {"version": "1.0.0"}}
    async def mock_get(*args, **kwargs): return MockResponse(200, mock_data)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    # prerelease
    res = await pypi_provider.get_package_metadata("pkg", installed_version="1.0.0a1")
    assert res.outdated == OutdatedStatus.TRUE

    # postrelease
    res2 = await pypi_provider.get_package_metadata("pkg", installed_version="1.0.0.post1")
    assert res2.outdated == OutdatedStatus.FALSE

@pytest.mark.asyncio
async def test_pypi_invalid_installed_version(pypi_provider, monkeypatch):
    mock_data = {"info": {"version": "1.0.0"}}
    async def mock_get(*args, **kwargs): return MockResponse(200, mock_data)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    # constraint
    res = await pypi_provider.get_package_metadata("pkg", installed_version=">=1.0.0")
    assert res.outdated == OutdatedStatus.UNKNOWN

    # wildcard
    res2 = await pypi_provider.get_package_metadata("pkg", installed_version="1.*")
    assert res2.outdated == OutdatedStatus.UNKNOWN

    res3 = await pypi_provider.get_package_metadata("pkg", installed_version="latest")
    assert res3.outdated == OutdatedStatus.UNKNOWN

@pytest.mark.asyncio
async def test_pypi_package_not_found(pypi_provider, monkeypatch):
    async def mock_get(*args, **kwargs): return MockResponse(404)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await pypi_provider.get_package_metadata("pkg", installed_version="1.0.0")
    assert res.status == RegistryStatus.NOT_FOUND

@pytest.mark.asyncio
async def test_pypi_rate_limited(pypi_provider, monkeypatch):
    async def mock_get(*args, **kwargs): return MockResponse(429)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await pypi_provider.get_package_metadata("pkg")
    assert res.status == RegistryStatus.RATE_LIMITED

@pytest.mark.asyncio
async def test_pypi_provider_unavailable_503(pypi_provider, monkeypatch):
    async def mock_get(*args, **kwargs): return MockResponse(503)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await pypi_provider.get_package_metadata("pkg")
    assert res.status == RegistryStatus.PROVIDER_UNAVAILABLE

@pytest.mark.asyncio
async def test_pypi_timeout(pypi_provider, monkeypatch):
    async def mock_get(*args, **kwargs): raise httpx.TimeoutException("Timeout")
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await pypi_provider.get_package_metadata("pkg")
    assert res.status == RegistryStatus.PROVIDER_UNAVAILABLE
    assert res.error_code == "TIMEOUT"

@pytest.mark.asyncio
async def test_pypi_network_error(pypi_provider, monkeypatch):
    async def mock_get(*args, **kwargs): raise httpx.RequestError("Network error")
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await pypi_provider.get_package_metadata("pkg")
    assert res.status == RegistryStatus.PROVIDER_UNAVAILABLE
    assert res.error_code == "NETWORK_ERROR"

@pytest.mark.asyncio
async def test_pypi_malformed_json(pypi_provider, monkeypatch):
    async def mock_get(*args, **kwargs): return MockResponse(200, "MALFORMED")
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await pypi_provider.get_package_metadata("pkg")
    assert res.status == RegistryStatus.INVALID_RESPONSE
    assert res.error_code == "MALFORMED_JSON"
