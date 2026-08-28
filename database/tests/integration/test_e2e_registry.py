import pytest
import asyncio
import httpx
from app.services.registry.npm import NpmRegistryProvider
from app.services.registry.pypi import PyPIRegistryProvider
from app.services.registry.base import OutdatedStatus

@pytest.mark.asyncio
async def test_live_npm_registry():
    provider = NpmRegistryProvider()

    try:
        # Test a real, stable package
        metadata = await provider.get_package_metadata("react", installed_version="18.2.0")

        assert metadata is not None
        assert metadata.latest_version is not None
        # react 18.2.0 is likely outdated, but we just verify it resolved successfully
        assert metadata.outdated in [OutdatedStatus.TRUE, OutdatedStatus.FALSE, OutdatedStatus.UNKNOWN]
        assert metadata.license is not None
        assert metadata.provider == "npm_registry"

    except httpx.HTTPError as e:
        pytest.skip(f"Live npm registry unavailable: {e}")

@pytest.mark.asyncio
async def test_live_pypi_registry():
    provider = PyPIRegistryProvider()

    try:
        # Test a real, stable package
        metadata = await provider.get_package_metadata("requests", installed_version="2.31.0")

        assert metadata is not None
        assert metadata.latest_version is not None
        assert metadata.outdated in [OutdatedStatus.TRUE, OutdatedStatus.FALSE, OutdatedStatus.UNKNOWN]
        assert metadata.license is not None
        assert metadata.provider == "pypi_registry"

    except httpx.HTTPError as e:
        pytest.skip(f"Live PyPI registry unavailable: {e}")
