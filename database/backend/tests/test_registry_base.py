from datetime import datetime, timezone
import pytest
from app.services.registry.base import (
    RegistryStatus,
    OutdatedStatus,
    NormalizedRegistryMetadata
)

def test_normalized_metadata_serialization():
    now = datetime.now(timezone.utc)
    metadata = NormalizedRegistryMetadata(
        ecosystem="npm",
        package_name="react",
        installed_version="18.2.0",
        latest_version="18.3.1",
        outdated=OutdatedStatus.TRUE,
        license="MIT",
        published_at=now,
        source="https://github.com/facebook/react",
        provider="npm_registry",
        fetched_at=now,
        status=RegistryStatus.SUCCESS
    )

    dump = metadata.model_dump()
    assert dump["ecosystem"] == "npm"
    assert dump["package_name"] == "react"
    assert dump["installed_version"] == "18.2.0"
    assert dump["outdated"] == OutdatedStatus.TRUE
    assert dump["status"] == RegistryStatus.SUCCESS

def test_unknown_outdated_state():
    now = datetime.now(timezone.utc)
    metadata = NormalizedRegistryMetadata(
        ecosystem="PyPI",
        package_name="requests",
        installed_version="^2.31.0",
        provider="pypi_registry",
        fetched_at=now,
        status=RegistryStatus.SUCCESS
    )

    assert metadata.outdated == OutdatedStatus.UNKNOWN
    assert metadata.latest_version is None

def test_provider_failure_state():
    now = datetime.now(timezone.utc)
    metadata = NormalizedRegistryMetadata(
        ecosystem="npm",
        package_name="unknown-package",
        provider="npm_registry",
        fetched_at=now,
        status=RegistryStatus.NOT_FOUND,
        error_code="404"
    )

    assert metadata.outdated == OutdatedStatus.UNKNOWN
    assert metadata.status == RegistryStatus.NOT_FOUND
    assert metadata.error_code == "404"
