"""Dashboard service."""

import uuid
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, distinct
from datetime import datetime, timedelta, timezone

from app.models.project import Project
from app.models.ecosystem import PackageEcosystem
from app.models.dependency import Dependency
from app.models.vulnerability import DependencyVulnerability, SeverityLevel
from app.models.audit import AuditLog
from app.models.scan import Scan, ScanStatus
from app.schemas.dashboard import DashboardSummary, SeriesPoint, ActivityItem

async def get_dashboard_summary(db: AsyncSession, organization_id: uuid.UUID) -> DashboardSummary:
    """Get the dashboard summary metrics for the given organization."""
    
    # 1. Tenant scoped base query criteria
    # Find all project IDs for this organization
    proj_stmt = select(Project.id).where(Project.organization_id == organization_id)
    project_ids = (await db.execute(proj_stmt)).scalars().all()
    
    if not project_ids:
        # Empty state handling
        return DashboardSummary(
            healthScore=None,
            totalDependencies=0,
            safePackages=0,
            vulnerablePackages=0,
            outdatedPackages=0,
            scansThisWeek=0,
            meanTimeToPatch="N/A",
            trend=[],
            severityBreakdown=[],
            ecosystemBreakdown=[],
            activity=[]
        )
        
    # Get latest successful scan per project
    latest_scans_raw = (await db.execute(
        select(Scan.project_id, Scan.id)
        .where(Scan.project_id.in_(project_ids), Scan.status == ScanStatus.COMPLETED)
        .order_by(Scan.project_id, Scan.created_at.desc())
    )).all()
    
    # Take first scan per project
    latest_scan_ids = []
    seen_projs = set()
    for proj_id, scan_id in latest_scans_raw:
        if proj_id not in seen_projs:
            seen_projs.add(proj_id)
            latest_scan_ids.append(scan_id)
            
    if not latest_scan_ids:
        return DashboardSummary(
            healthScore=None,
            totalDependencies=0,
            safePackages=0,
            vulnerablePackages=0,
            outdatedPackages=0,
            scansThisWeek=0,
            meanTimeToPatch="N/A",
            trend=[],
            severityBreakdown=[],
            ecosystemBreakdown=[],
            activity=[]
        )
        
    # 2. Total Dependencies (SQL COUNT)
    deps_count_stmt = select(func.count(Dependency.id)).where(Dependency.scan_id.in_(latest_scan_ids))
    total_deps = (await db.execute(deps_count_stmt)).scalar() or 0
    
    # Ecosystem breakdown
    eco_group_stmt = (
        select(PackageEcosystem.name, func.count(Dependency.id))
        .join(Dependency, Dependency.ecosystem_id == PackageEcosystem.id)
        .where(Dependency.scan_id.in_(latest_scan_ids))
        .group_by(PackageEcosystem.name)
        .order_by(desc(func.count(Dependency.id)))
    )
    eco_counts_raw = (await db.execute(eco_group_stmt)).all()
    
    ecosystemBreakdown = [
        SeriesPoint(label=eco_name, value=count)
        for eco_name, count in eco_counts_raw
    ]

    # 3. Vulnerable Packages & Severity Breakdown
    vuln_count_stmt = select(func.count(distinct(DependencyVulnerability.dependency_id))).where(DependencyVulnerability.scan_id.in_(latest_scan_ids))
    vulnerable_deps = (await db.execute(vuln_count_stmt)).scalar() or 0
    
    safe_deps = total_deps - vulnerable_deps
    
    sev_group_stmt = (
        select(DependencyVulnerability.severity, func.count(DependencyVulnerability.id))
        .where(DependencyVulnerability.scan_id.in_(latest_scan_ids))
        .group_by(DependencyVulnerability.severity)
    )
    sev_counts_raw = (await db.execute(sev_group_stmt)).all()
    
    sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for sev_level, count in sev_counts_raw:
        if sev_level.name in sev_counts:
            sev_counts[sev_level.name] += count
            
    severityBreakdown = [
        SeriesPoint(label="Critical", value=sev_counts["CRITICAL"]),
        SeriesPoint(label="High", value=sev_counts["HIGH"]),
        SeriesPoint(label="Medium", value=sev_counts["MEDIUM"]),
        SeriesPoint(label="Low", value=sev_counts["LOW"]),
    ]
    
    # 4. Scans this week
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    scans_week_stmt = select(func.count(Scan.id)).where(
        Scan.project_id.in_(project_ids),
        Scan.created_at >= one_week_ago
    )
    scans_this_week = (await db.execute(scans_week_stmt)).scalar() or 0
    
    # 5. Activity (Audit Logs)
    audit_stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    audit_logs = (await db.execute(audit_stmt)).scalars().all()
    
    activity = []
    for log in audit_logs:
        # map category to activity type: "scan" | "repo" | "user" | "vuln" | "report"
        act_type = "user"
        if "SCAN" in log.action.name:
            act_type = "scan"
        elif "PROJECT" in log.action.name or "ARTIFACT" in log.action.name:
            act_type = "repo"
            
        activity.append(ActivityItem(
            id=str(log.id),
            type=act_type,
            message=log.action.name.replace("_", " ").title(),
            actor=str(log.user_id) if log.user_id else "System",
            timestamp=log.created_at.isoformat()
        ))
        
    return DashboardSummary(
        healthScore=None,  # DEFERRED
        totalDependencies=total_deps,
        safePackages=safe_deps,
        vulnerablePackages=vulnerable_deps,
        outdatedPackages=0,  # DEFERRED
        scansThisWeek=scans_this_week,
        meanTimeToPatch="N/A",  # DEFERRED
        trend=[],  # DEFERRED
        severityBreakdown=severityBreakdown,
        ecosystemBreakdown=ecosystemBreakdown,
        activity=activity
    )
