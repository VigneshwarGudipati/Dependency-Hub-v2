from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class DependencyPackage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    installedVersion: str
    latestVersion: str  # DEFERRED
    status: str  # safe, outdated, vulnerable
    severity: Optional[str] = None
    cve: Optional[str] = None
    license: str
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
