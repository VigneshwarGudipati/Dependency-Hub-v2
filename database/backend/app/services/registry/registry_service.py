import asyncio
import enum
import logging
import uuid
from datetime import timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import utc_now
from app.models.registry_cache import RegistryCache
from app.services.registry.base import (
    NormalizedRegistryMetadata,
    RegistryProviderBase,
    RegistryStatus,
    OutdatedStatus,
)
from app.services.registry.npm import NpmRegistryProvider
from app.services.registry.pypi import PyPIRegistryProvider

logger = logging.getLogger(__name__)

class CacheState(str, enum.Enum):
    MISS = "MISS"
    FRESH = "FRESH"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"

# Module-level dictionary for in-flight request deduplication
_in_flight_requests: Dict[Tuple[str, str], asyncio.Future] = {}

class RegistryIntelligenceService:
    def __init__(self, session: AsyncSession, cache_ttl_seconds: int = 3600):
        self.session = session
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.providers: Dict[str, RegistryProviderBase] = {
            "npm": NpmRegistryProvider(),
            "pypi": PyPIRegistryProvider(),
        }

    def _normalize_ecosystem(self, ecosystem: str) -> str:
        return ecosystem.strip().lower()

    def _get_provider(self, ecosystem: str) -> Optional[RegistryProviderBase]:
        eco_norm = self._normalize_ecosystem(ecosystem)
        return self.providers.get(eco_norm)

    async def get_package_metadata(
        self, ecosystem: str, package_name: str, installed_version: Optional[str] = None
    ) -> Tuple[NormalizedRegistryMetadata, CacheState]:
        eco_norm = self._normalize_ecosystem(ecosystem)
        provider = self._get_provider(ecosystem)

        now = utc_now()

        if not provider:
            meta = NormalizedRegistryMetadata(
                ecosystem=ecosystem,
                package_name=package_name,
                installed_version=installed_version,
                provider="unknown",
                fetched_at=now,
                status=RegistryStatus.UNSUPPORTED_REQUEST,
                error_code="UNSUPPORTED_ECOSYSTEM",
            )
            return meta, CacheState.UNAVAILABLE

        cache_key = (eco_norm, package_name)

        # 1. Check cache
        stmt = select(RegistryCache).where(
            RegistryCache.ecosystem == eco_norm,
            RegistryCache.package_name == package_name,
        )
        result = await self.session.execute(stmt)
        cached_record = result.scalars().first()

        stale_meta = None
        if cached_record and cached_record.registry_metadata:
            is_fresh = cached_record.expires_at > now
            if is_fresh:
                meta = NormalizedRegistryMetadata.model_validate(cached_record.registry_metadata)
                meta.installed_version = installed_version
                if installed_version and meta.latest_version:
                    meta.outdated = provider._compare_versions(installed_version, meta.latest_version)
                return meta, CacheState.FRESH
            else:
                stale_meta = NormalizedRegistryMetadata.model_validate(cached_record.registry_metadata)
                stale_meta.installed_version = installed_version
                if installed_version and stale_meta.latest_version:
                    stale_meta.outdated = provider._compare_versions(installed_version, stale_meta.latest_version)

        # 2. In-flight deduplication
        if cache_key in _in_flight_requests:
            try:
                meta = await _in_flight_requests[cache_key]
                ret_meta = meta.model_copy()
                ret_meta.installed_version = installed_version
                if installed_version and ret_meta.latest_version:
                    ret_meta.outdated = provider._compare_versions(installed_version, ret_meta.latest_version)
                return ret_meta, CacheState.FRESH
            except Exception as e:
                logger.error(f"In-flight request failed: {e}")

        future = asyncio.Future()
        _in_flight_requests[cache_key] = future

        try:
            # 3. Fetch from provider (without installed version so we cache the generic package info)
            meta = await provider.get_package_metadata(package_name, installed_version=None)

            # Fallback to stale if provider fails with an error where stale is better than nothing
            if meta.status in (RegistryStatus.PROVIDER_UNAVAILABLE, RegistryStatus.RATE_LIMITED, RegistryStatus.INVALID_RESPONSE):
                if stale_meta:
                    future.set_result(stale_meta)
                    return stale_meta, CacheState.STALE

            # Save to cache if successful or if it's a definitive result (NOT_FOUND)
            if meta.status in (RegistryStatus.SUCCESS, RegistryStatus.NOT_FOUND):
                expires_at = now + self.cache_ttl

                stmt_upsert = insert(RegistryCache).values(
                    id=uuid.uuid4(),
                    ecosystem=eco_norm,
                    package_name=package_name,
                    status=meta.status,
                    registry_metadata=meta.model_dump(mode="json"),
                    fetched_at=now,
                    expires_at=expires_at,
                    created_at=now,
                    updated_at=now,
                ).on_conflict_do_update(
                    index_elements=["ecosystem", "package_name"],
                    set_={
                        "status": meta.status,
                        "metadata": meta.model_dump(mode="json"),
                        "fetched_at": now,
                        "expires_at": expires_at,
                        "updated_at": now,
                    },
                )
                await self.session.execute(stmt_upsert)
                await self.session.flush()

            future.set_result(meta)

            ret_meta = meta.model_copy()
            ret_meta.installed_version = installed_version
            if installed_version and ret_meta.latest_version:
                ret_meta.outdated = provider._compare_versions(installed_version, ret_meta.latest_version)

            # Even if provider failed, if we don't have stale, we return MISS with the error metadata
            return ret_meta, CacheState.MISS

        except Exception as e:
            if not future.done():
                future.set_exception(e)
                future.exception()  # Prevent "Future exception was never retrieved" warning
            if stale_meta:
                return stale_meta, CacheState.STALE
            raise
        finally:
            _in_flight_requests.pop(cache_key, None)
