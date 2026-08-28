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

logger = logging.getLogger(__name__)

class PyPIRegistryProvider(RegistryProviderBase):
    def __init__(self, base_url: str = "https://pypi.org/pypi"):
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "pypi_registry"

    def _is_concrete_version(self, version: str) -> bool:
        """Check if the provided version is concrete for PyPI PEP-440."""
        if not version:
            return False
        v = version.strip().lower()
        if v in ("*", "latest"):
            return False
        # Exclude constraint operators and wildcard indicators
        if any(c in v for c in ("<", ">", "=", "~", "^", "*", "x")):
            return False
        try:
            parse_version(v)
            return True
        except InvalidVersion:
            return False

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
            # PyPI uses ISO format: 2023-05-22T16:16:03.111425Z
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def get_package_metadata(self, package_name: str, installed_version: Optional[str] = None) -> NormalizedRegistryMetadata:
        now = datetime.now(timezone.utc)
        base_meta = NormalizedRegistryMetadata(
            ecosystem="PyPI",
            package_name=package_name,
            installed_version=installed_version,
            latest_version=None,
            outdated=OutdatedStatus.UNKNOWN,
            provider=self.provider_name,
            fetched_at=now,
            status=RegistryStatus.SUCCESS
        )

        if not package_name:
            base_meta.status = RegistryStatus.INVALID_RESPONSE
            base_meta.error_code = "INVALID_PACKAGE_NAME"
            return base_meta

        import urllib.parse
        encoded_package = urllib.parse.quote(package_name, safe='')
        url = f"{self.base_url}/{encoded_package}/json"

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

                info = data.get("info", {})
                if not isinstance(info, dict):
                    base_meta.status = RegistryStatus.INVALID_RESPONSE
                    return base_meta

                # Extract latest version
                latest_ver = info.get("version")
                if isinstance(latest_ver, str):
                    base_meta.latest_version = latest_ver

                if base_meta.latest_version and installed_version:
                    base_meta.outdated = self._compare_versions(installed_version, base_meta.latest_version)

                # License
                license_data = info.get("license")
                if isinstance(license_data, str) and license_data.strip() and license_data.strip().lower() != "unknown":
                    base_meta.license = license_data.strip()

                # Repository / Source
                repo_url = info.get("home_page")
                project_urls = info.get("project_urls")
                if isinstance(project_urls, dict):
                    repo_url = project_urls.get("Source") or project_urls.get("Repository") or repo_url
                if isinstance(repo_url, str) and repo_url.strip():
                    base_meta.source = repo_url.strip()

                # Publication metadata
                releases = data.get("releases", {})
                if base_meta.latest_version and isinstance(releases, dict):
                    latest_release = releases.get(base_meta.latest_version)
                    if isinstance(latest_release, list) and len(latest_release) > 0:
                        first_file = latest_release[0]
                        if isinstance(first_file, dict):
                            pub_time_str = first_file.get("upload_time_iso_8601")
                            base_meta.published_at = self._parse_datetime(pub_time_str)

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
