from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class DependencyPackage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    installedVersion: str
    latestVersion: Optional[str] = None
    status: str  # safe, outdated, vulnerable
    severity: Optional[str] = None
    cve: Optional[str] = None
    license: str
    outdated: Optional[str] = None
    publishedAt: Optional[str] = None
    registrySource: Optional[str] = None
    registryStatus: Optional[str] = None
    weeklyDownloads: int  # DEFERRED
    maintainers: int  # DEFERRED
    lastPublished: str  # DEFERRED
    size: str  # DEFERRED
    description: str  # DEFERRED
    recommendation: str  # DEFERRED
    healthScore: int  # DEFERRED
    dependents: List[str]
    repository: str
    direct: bool
