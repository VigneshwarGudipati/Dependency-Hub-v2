from typing import List, Optional
from pydantic import BaseModel


class SeriesPoint(BaseModel):
    label: str
    value: int
    secondary: Optional[int] = None


class ActivityItem(BaseModel):
    id: str
    type: str  # "scan" | "repo" | "user" | "vuln" | "report"
    message: str
    actor: str
    timestamp: str


class DashboardSummary(BaseModel):
    healthScore: Optional[int] = None
    totalDependencies: int
    safePackages: int
    vulnerablePackages: int
    outdatedPackages: int
    scansThisWeek: int
    meanTimeToPatch: str
    trend: List[SeriesPoint]
    severityBreakdown: List[SeriesPoint]
    ecosystemBreakdown: List[SeriesPoint]
    activity: List[ActivityItem]
