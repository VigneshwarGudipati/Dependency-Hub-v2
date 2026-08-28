import enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from abc import ABC, abstractmethod

class RegistryStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    UNSUPPORTED_REQUEST = "UNSUPPORTED_REQUEST"

class OutdatedStatus(str, enum.Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"

class NormalizedRegistryMetadata(BaseModel):
    ecosystem: str
    package_name: str
    installed_version: Optional[str] = None
    latest_version: Optional[str] = None
    outdated: OutdatedStatus = OutdatedStatus.UNKNOWN
    license: Optional[str] = None
    published_at: Optional[datetime] = None
    source: Optional[str] = None
    provider: str
    fetched_at: datetime
    status: RegistryStatus
    error_code: Optional[str] = None

class RegistryProviderBase(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'npm', 'PyPI')"""
        pass

    @abstractmethod
    async def get_package_metadata(self, package_name: str, installed_version: Optional[str] = None) -> NormalizedRegistryMetadata:
        """Fetch and normalize package metadata from the registry."""
        pass
