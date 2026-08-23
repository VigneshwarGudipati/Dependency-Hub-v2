import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.vulnerability.osv_provider import OSVProvider
import httpx

@pytest.fixture
def osv_provider():
    return OSVProvider()

class MockResponse:
    def __init__(self, json_data, status_code):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.osv.dev")
            raise httpx.HTTPStatusError("Error", request=request, response=httpx.Response(self.status_code, request=request))

@pytest.mark.asyncio
async def test_match_batch_empty(osv_provider):
    res = await osv_provider.match_batch([])
    assert res == {}

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch("httpx.AsyncClient.get")
async def test_match_batch_success(mock_get, mock_post, osv_provider):
    # successful findings response
    mock_post.return_value = MockResponse({
        "results": [
            {"vulns": [{"id": "GHSA-123", "modified": "2023"}]}
        ]
    }, 200)

    mock_get.return_value = MockResponse({
        "id": "GHSA-123",
        "aliases": ["CVE-2023-123"],
        "summary": "Mock vuln",
        "database_specific": {"severity": "CRITICAL"}
    }, 200)

    dep = MagicMock()
    dep.id = "dep-1"
    dep.ecosystem.name = "npm"
    dep.package_name = "axios"
    dep.version_constraint = "1.0.0"

    res = await osv_provider.match_batch([dep])
    assert "dep-1" in res
    assert len(res["dep-1"]) == 1

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch("httpx.AsyncClient.get")
async def test_match_batch_duplicate_advisory(mock_get, mock_post, osv_provider):
    # duplicate advisory IDs
    mock_post.return_value = MockResponse({
        "results": [
            {"vulns": [{"id": "GHSA-123", "modified": "2023"}, {"id": "GHSA-123", "modified": "2023"}]}
        ]
    }, 200)

    mock_get.return_value = MockResponse({
        "id": "GHSA-123",
        "aliases": ["CVE-2023-123"],
        "summary": "Mock vuln",
        "database_specific": {"severity": "CRITICAL"}
    }, 200)

    dep = MagicMock()
    dep.id = "dep-1"
    dep.ecosystem.name = "npm"
    dep.package_name = "axios"
    dep.version_constraint = "1.0.0"

    res = await osv_provider.match_batch([dep])
    assert "dep-1" in res
    assert len(res["dep-1"]) == 1 # Deduplicated

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_match_batch_429(mock_post, osv_provider):
    # batch query 429
    mock_post.return_value = MockResponse({}, 429)

    dep = MagicMock()
    dep.ecosystem.name = "npm"
    dep.package_name = "axios"
    dep.version_constraint = "1.0.0"

    with pytest.raises(RuntimeError, match="PROVIDER_UNAVAILABLE"):
        await osv_provider.match_batch([dep])

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_match_batch_500(mock_post, osv_provider):
    # batch query 500
    mock_post.return_value = MockResponse({}, 500)

    dep = MagicMock()
    dep.ecosystem.name = "npm"
    dep.package_name = "axios"
    dep.version_constraint = "1.0.0"

    with pytest.raises(RuntimeError, match="INVALID_PROVIDER_RESPONSE"):
        await osv_provider.match_batch([dep])

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch("httpx.AsyncClient.get")
async def test_detail_endpoint_429(mock_get, mock_post, osv_provider):
    # detail endpoint 429
    mock_post.return_value = MockResponse({"results": [{"vulns": [{"id": "GHSA-123"}]}]}, 200)
    mock_get.return_value = MockResponse({}, 429)

    dep = MagicMock()
    dep.ecosystem.name = "npm"
    dep.package_name = "axios"
    dep.version_constraint = "1.0.0"

    with pytest.raises(RuntimeError, match="PROVIDER_UNAVAILABLE"):
        await osv_provider.match_batch([dep])

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch("httpx.AsyncClient.get")
async def test_detail_endpoint_500(mock_get, mock_post, osv_provider):
    # detail endpoint 500
    mock_post.return_value = MockResponse({"results": [{"vulns": [{"id": "GHSA-123"}]}]}, 200)
    mock_get.return_value = MockResponse({}, 500)

    dep = MagicMock()
    dep.ecosystem.name = "npm"
    dep.package_name = "axios"
    dep.version_constraint = "1.0.0"

    with pytest.raises(RuntimeError, match="INVALID_PROVIDER_RESPONSE"):
        await osv_provider.match_batch([dep])

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch("httpx.AsyncClient.get")
async def test_detail_network_failure(mock_get, mock_post, osv_provider):
    # detail network failure
    mock_post.return_value = MockResponse({"results": [{"vulns": [{"id": "GHSA-123"}]}]}, 200)
    mock_get.side_effect = httpx.RequestError("Network timeout")

    dep = MagicMock()
    dep.ecosystem.name = "npm"
    dep.package_name = "axios"
    dep.version_constraint = "1.0.0"

    with pytest.raises(RuntimeError, match="PROVIDER_UNAVAILABLE"):
        await osv_provider.match_batch([dep])

@pytest.mark.asyncio
async def test_invalid_missing_version(osv_provider):
    # invalid/missing version
    dep = MagicMock()
    dep.ecosystem.name = "npm"
    dep.package_name = "axios"
    dep.version_constraint = None
    dep.package_version = "*"

    with pytest.raises(RuntimeError, match="INVALID_VERSION"):
        await osv_provider.match_batch([dep])

@pytest.mark.asyncio
async def test_unsupported_ecosystem(osv_provider):
    # unsupported ecosystem
    dep = MagicMock()
    dep.ecosystem.name = "unknown_eco"
    dep.package_name = "axios"
    dep.version_constraint = "1.0.0"

    with pytest.raises(RuntimeError, match="UNSUPPORTED_ECOSYSTEM"):
        await osv_provider.match_batch([dep])

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_successful_no_findings(mock_post, osv_provider):
    # successful no-findings response
    mock_post.return_value = MockResponse({"results": [{}]}, 200)

    dep = MagicMock()
    dep.id = "dep-1"
    dep.ecosystem.name = "npm"
    dep.package_name = "axios"
    dep.version_constraint = "1.0.0"

    res = await osv_provider.match_batch([dep])
    assert res == {}
