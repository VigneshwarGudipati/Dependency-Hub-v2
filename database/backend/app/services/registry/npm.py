import logging
from datetime import datetime, timezone
from typing import Optional
from packaging.version import parse as parse_version, InvalidVersion
import httpx

from app.services.registry.base import (
    RegistryProviderBase,
    NormalizedRegistryMetadata,
    RegistryStatus,
    OutdatedStatus
)

import re

logger = logging.getLogger(__name__)

class NpmRegistryProvider(RegistryProviderBase):
    _SEMVER_CONCRETE_REGEX = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")

    def __init__(self, base_url: str = "https://registry.npmjs.org"):
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "npm_registry"

    def _is_concrete_version(self, version: str) -> bool:
        """Check if the provided version is concrete, excluding constraints like ^, ~, >=, 1.x, etc."""
        if not version:
            return False
        return bool(self._SEMVER_CONCRETE_REGEX.match(version.strip()))

    def _compare_versions(self, installed: str, latest: str) -> OutdatedStatus:
        if not self._is_concrete_version(installed):
            return OutdatedStatus.UNKNOWN

        try:
            v_inst = parse_version(installed)
            v_latest = parse_version(latest)
            if v_inst < v_latest:
                return OutdatedStatus.TRUE
            return OutdatedStatus.FALSE
        except InvalidVersion:
            return OutdatedStatus.UNKNOWN

    def _parse_datetime(self, time_str: Optional[str]) -> Optional[datetime]:
        if not time_str:
            return None
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def get_package_metadata(self, package_name: str, installed_version: Optional[str] = None) -> NormalizedRegistryMetadata:
        now = datetime.now(timezone.utc)
        base_meta = NormalizedRegistryMetadata(
            ecosystem="npm",
            package_name=package_name,
            installed_version=installed_version,
            latest_version=None,
            outdated=OutdatedStatus.UNKNOWN,
            provider=self.provider_name,
            fetched_at=now,
            status=RegistryStatus.SUCCESS
        )

        if not package_name or "/" in package_name and not package_name.startswith("@"):
            base_meta.status = RegistryStatus.INVALID_RESPONSE
            base_meta.error_code = "INVALID_PACKAGE_NAME"
            return base_meta

        import urllib.parse
        encoded_package = urllib.parse.quote(package_name, safe='@/')
        url = f"{self.base_url}/{encoded_package}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)

                if resp.status_code == 404:
                    base_meta.status = RegistryStatus.NOT_FOUND
                    base_meta.error_code = "404"
                    return base_meta

                if resp.status_code == 429:
                    base_meta.status = RegistryStatus.RATE_LIMITED
                    base_meta.error_code = "429"
                    return base_meta

                resp.raise_for_status()
                data = resp.json()

                if not isinstance(data, dict):
                    base_meta.status = RegistryStatus.INVALID_RESPONSE
                    return base_meta

                # Extract latest version
                latest_ver = None
                dist_tags = data.get("dist-tags", {})
                if isinstance(dist_tags, dict):
                    latest_ver = dist_tags.get("latest")

                base_meta.latest_version = latest_ver

                if latest_ver and installed_version:
                    base_meta.outdated = self._compare_versions(installed_version, latest_ver)

                # License
                license_data = data.get("license")
                if isinstance(license_data, str):
                    base_meta.license = license_data
                elif isinstance(license_data, dict):
                    base_meta.license = license_data.get("type")

                # Publication metadata
                time_data = data.get("time", {})
                if latest_ver and isinstance(time_data, dict):
                    pub_time_str = time_data.get(latest_ver)
                    base_meta.published_at = self._parse_datetime(pub_time_str)

                # Repository / Source
                repo_data = data.get("repository")
                if isinstance(repo_data, dict):
                    url_str = repo_data.get("url")
                    if isinstance(url_str, str):
                        base_meta.source = url_str
                elif isinstance(repo_data, str):
                    base_meta.source = repo_data

                return base_meta

        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                base_meta.status = RegistryStatus.PROVIDER_UNAVAILABLE
                base_meta.error_code = str(e.response.status_code)
            else:
                base_meta.status = RegistryStatus.INVALID_RESPONSE
                base_meta.error_code = str(e.response.status_code)
        except httpx.TimeoutException:
            base_meta.status = RegistryStatus.PROVIDER_UNAVAILABLE
            base_meta.error_code = "TIMEOUT"
        except httpx.RequestError:
            base_meta.status = RegistryStatus.PROVIDER_UNAVAILABLE
            base_meta.error_code = "NETWORK_ERROR"
        except ValueError:
            base_meta.status = RegistryStatus.INVALID_RESPONSE
            base_meta.error_code = "MALFORMED_JSON"

        return base_meta
