import pytest
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.registry.registry_service import RegistryIntelligenceService, CacheState
from app.services.registry.base import NormalizedRegistryMetadata, RegistryStatus, OutdatedStatus
from app.models.registry_cache import RegistryCache
from app.models.base import utc_now

class MockScalars:
    def __init__(self, obj):
        self.obj = obj
    def first(self):
        return self.obj

class MockResult:
    def __init__(self, obj=None):
        self.obj = obj
    def scalars(self):
        return MockScalars(self.obj)

@pytest.fixture
def db_session():
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = MockResult(None) # Default to MISS
    return session

@pytest.fixture
def registry_service(db_session: AsyncSession):
    return RegistryIntelligenceService(session=db_session, cache_ttl_seconds=3600)

def create_mock_metadata(ecosystem, package, status=RegistryStatus.SUCCESS, latest="2.0.0"):
    return NormalizedRegistryMetadata(
        ecosystem=ecosystem,
        package_name=package,
        installed_version=None,
        latest_version=latest,
        outdated=OutdatedStatus.UNKNOWN,
        provider="mock_provider",
        fetched_at=utc_now(),
        status=status,
    )

@pytest.mark.asyncio
async def test_registry_service_unsupported_ecosystem(registry_service):
    meta, state = await registry_service.get_package_metadata("maven", "spring-core")
    assert state == CacheState.UNAVAILABLE
    assert meta.status == RegistryStatus.UNSUPPORTED_REQUEST

@pytest.mark.asyncio
async def test_registry_service_cache_miss(registry_service, monkeypatch, db_session):
    mock_meta = create_mock_metadata("npm", "react")
    mock_get = AsyncMock(return_value=mock_meta)

    # Mock the npm provider instance
    provider = registry_service.providers["npm"]
    monkeypatch.setattr(provider, "get_package_metadata", mock_get)

    # Call service
    meta, state = await registry_service.get_package_metadata("npm", "react", "1.0.0")

    assert state == CacheState.MISS
    assert meta.package_name == "react"
    mock_get.assert_called_once()

    # Check DB was interacted with (1 select, 1 insert)
    assert db_session.execute.call_count == 2
    db_session.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_registry_service_cache_hit(registry_service, monkeypatch, db_session):
    mock_meta = create_mock_metadata("npm", "react")
    mock_get = AsyncMock(return_value=mock_meta)
    monkeypatch.setattr(registry_service.providers["npm"], "get_package_metadata", mock_get)

    # First call - MISS
    meta1, state1 = await registry_service.get_package_metadata("npm", "react", "1.0.0")
    assert state1 == CacheState.MISS

    # Reset mock and configure DB to return hit
    mock_get.reset_mock()

    cached_record = RegistryCache(
        ecosystem="npm",
        package_name="react",
        expires_at=utc_now() + timedelta(hours=1),
        registry_metadata=mock_meta.model_dump(mode="json")
    )
    db_session.execute.return_value = MockResult(cached_record)

    # Second call - FRESH hit
    meta2, state2 = await registry_service.get_package_metadata("npm", "react", "1.5.0")
    assert state2 == CacheState.FRESH
    assert meta2.installed_version == "1.5.0"
    mock_get.assert_not_called()

@pytest.mark.asyncio
async def test_registry_service_duplicate_requests(registry_service, monkeypatch):
    mock_meta = create_mock_metadata("pypi", "requests")

    # Make the mock slow to ensure in-flight capture
    async def slow_mock(*args, **kwargs):
        await asyncio.sleep(0.1)
        return mock_meta

    monkeypatch.setattr(registry_service.providers["pypi"], "get_package_metadata", slow_mock)

    # Launch two concurrent requests
    task1 = asyncio.create_task(registry_service.get_package_metadata("PyPI", "requests", "1.0.0"))
    task2 = asyncio.create_task(registry_service.get_package_metadata("pypi", "requests", "1.0.0"))

    results = await asyncio.gather(task1, task2)

    # One should be MISS (did the actual work), one should be FRESH (deduplicated)
    states = [res[1] for res in results]
    assert CacheState.MISS in states
    assert CacheState.FRESH in states

@pytest.mark.asyncio
async def test_registry_service_provider_failure_no_stale(registry_service, monkeypatch):
    mock_meta = create_mock_metadata("npm", "react", status=RegistryStatus.PROVIDER_UNAVAILABLE)
    mock_get = AsyncMock(return_value=mock_meta)
    monkeypatch.setattr(registry_service.providers["npm"], "get_package_metadata", mock_get)

    meta, state = await registry_service.get_package_metadata("npm", "react")

    # Without stale data, it returns MISS and the error metadata
    assert state == CacheState.MISS
    assert meta.status == RegistryStatus.PROVIDER_UNAVAILABLE

@pytest.mark.asyncio
async def test_registry_service_provider_failure_with_stale(registry_service, monkeypatch, db_session):
    # Setup stale cache in DB
    now = utc_now()
    past = now - timedelta(days=2)

    stale_meta = create_mock_metadata("npm", "react", latest="1.0.0")
    stale_meta.fetched_at = past

    cached_record = RegistryCache(
        ecosystem="npm",
        package_name="react",
        expires_at=past, # Expired
        registry_metadata=stale_meta.model_dump(mode="json")
    )
    db_session.execute.return_value = MockResult(cached_record)

    # Mock provider failure
    fail_meta = create_mock_metadata("npm", "react", status=RegistryStatus.PROVIDER_UNAVAILABLE)
    mock_get = AsyncMock(return_value=fail_meta)
    monkeypatch.setattr(registry_service.providers["npm"], "get_package_metadata", mock_get)

    # Fetch
    meta, state = await registry_service.get_package_metadata("npm", "react", "0.9.0")

    assert state == CacheState.STALE
    assert meta.latest_version == "1.0.0"
    assert meta.fetched_at == past
    # Outdated should still calculate based on stale
    assert meta.outdated == OutdatedStatus.TRUE
