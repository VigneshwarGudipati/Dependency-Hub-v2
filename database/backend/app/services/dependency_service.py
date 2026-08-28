import uuid
import math
from typing import Optional, List, Tuple
from sqlalchemy import select, func, desc, null, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.dependency import Dependency, DependencyEdge, RelationshipType
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.models.vulnerability import DependencyVulnerability
from app.schemas.dependency import DependencyPackage
from app.schemas.graph import GraphResponse, GraphNode, GraphEdge
from app.schemas.pagination import PaginatedResponse

async def get_latest_scans_for_org(db: AsyncSession, organization_id: uuid.UUID, project_id: Optional[uuid.UUID] = None) -> List[uuid.UUID]:
    proj_stmt = select(Project.id).where(Project.organization_id == organization_id)
    if project_id:
        proj_stmt = proj_stmt.where(Project.id == project_id)
    project_ids = (await db.execute(proj_stmt)).scalars().all()

    if not project_ids:
        return []

    scan_stmt = (
        select(Scan.project_id, Scan.id)
        .where(Scan.project_id.in_(project_ids), Scan.status == ScanStatus.COMPLETED)
        .order_by(Scan.project_id, Scan.completed_at.desc(), Scan.created_at.desc())
    )
    scans_raw = (await db.execute(scan_stmt)).all()
    seen_projs = set()
    latest_scan_ids = []
    for pid, sid in scans_raw:
        if pid not in seen_projs:
            seen_projs.add(pid)
            latest_scan_ids.append(sid)
    return latest_scan_ids

async def list_dependencies(
    db: AsyncSession,
    organization_id: uuid.UUID,
    page: int = 1,
    page_size: int = 25,
    query: Optional[str] = None,
    status: Optional[str] = None, # "safe", "outdated", "vulnerable", "all"
    project_id: Optional[uuid.UUID] = None
) -> PaginatedResponse[DependencyPackage]:

    latest_scan_ids = await get_latest_scans_for_org(db, organization_id, project_id)
    if not latest_scan_ids:
        return PaginatedResponse(items=[], page=page, page_size=page_size, total=0, total_pages=0)

    stmt = (
        select(Dependency)
        .options(
            joinedload(Dependency.project),
            selectinload(Dependency.vulnerabilities).joinedload(DependencyVulnerability.vulnerability)
        )
        .where(Dependency.scan_id.in_(latest_scan_ids))
    )

    if query:
        stmt = stmt.where(Dependency.package_name.ilike(f"%{query}%"))

    # We load all matching to handle the "status" filter which might depend on vulnerabilities.
    # To do it in SQL:
    if status == "vulnerable":
        stmt = stmt.join(DependencyVulnerability, Dependency.id == DependencyVulnerability.dependency_id).distinct()
    elif status == "safe":
        stmt = stmt.outerjoin(DependencyVulnerability, Dependency.id == DependencyVulnerability.dependency_id).where(DependencyVulnerability.id == null())
    elif status == "outdated":
        stmt = stmt.where(Dependency.dependency_metadata["registry"]["outdated"].astext == "true")

    # Order by package name
    stmt = stmt.order_by(Dependency.package_name)

    # Pagination counts
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    # Apply limit/offset
    stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    dependencies = (await db.execute(stmt)).scalars().all()

    items = []
    for dep in dependencies:
        vulns = dep.vulnerabilities
        is_vuln = len(vulns) > 0
        computed_status = "vulnerable" if is_vuln else "safe"

        # Take the highest severity
        severity = None
        cve = None
        if is_vuln:
            severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
            sorted_vulns = sorted(vulns, key=lambda v: severity_order.get(v.vulnerability.severity.name, 0), reverse=True)
            severity = sorted_vulns[0].vulnerability.severity.name.lower()
            cve = sorted_vulns[0].vulnerability.vulnerability_id

        reg = dep.dependency_metadata.get("registry", {})

        items.append(DependencyPackage(
            id=str(dep.id),
            name=dep.package_name,
            installedVersion=dep.package_version,
            latestVersion=reg.get("latest_version"),
            status=computed_status,
            severity=severity,
            cve=cve,
            license=dep.license or "Unknown",
            outdated=reg.get("outdated"),
            publishedAt=reg.get("published_at"),
            registrySource=reg.get("provider"),
            registryStatus=reg.get("status"),
            weeklyDownloads=0,
            maintainers=0,
            lastPublished="N/A",
            size="N/A",
            description="",
            recommendation="",
            healthScore=0,
            dependents=[],
            repository=dep.project.name,
            direct=dep.is_direct
        ))

    return PaginatedResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages
    )

async def get_dependency_detail(
    db: AsyncSession,
    organization_id: uuid.UUID,
    dependency_id: uuid.UUID
) -> Optional[DependencyPackage]:
    # 1. Fetch the dependency
    stmt = (
        select(Dependency)
        .options(
            joinedload(Dependency.project),
            selectinload(Dependency.vulnerabilities).joinedload(DependencyVulnerability.vulnerability),
            selectinload(Dependency.incoming_edges).joinedload(DependencyEdge.parent_dependency)
        )
        .where(Dependency.id == dependency_id)
    )
    dep = (await db.execute(stmt)).scalar_one_or_none()
    if not dep:
        return None

    # 2. Enforce tenant isolation via the project
    if dep.project.organization_id != organization_id:
        return None

    # 3. Check if it belongs to the *latest* scan for that project (optional, but good for consistency)
    latest_scan_ids = await get_latest_scans_for_org(db, organization_id, dep.project_id)
    if dep.scan_id not in latest_scan_ids:
        # Strictly speaking, if they request an older dependency by explicit ID, we might allow it.
        # But Phase 6B says "Do not mix historical scan dependency rows into the current package list."
        # If it's a detail fetch by exact ID, they likely clicked it from the list.
        pass

    vulns = dep.vulnerabilities
    is_vuln = len(vulns) > 0
    computed_status = "vulnerable" if is_vuln else "safe"

    severity = None
    cve = None
    if is_vuln:
        severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        sorted_vulns = sorted(vulns, key=lambda v: severity_order.get(v.vulnerability.severity.name, 0), reverse=True)
        severity = sorted_vulns[0].vulnerability.severity.name.lower()
        cve = sorted_vulns[0].vulnerability.vulnerability_id

    dependents = [edge.parent_dependency.package_name for edge in dep.incoming_edges]

    reg = dep.dependency_metadata.get("registry", {})

    return DependencyPackage(
        id=str(dep.id),
        name=dep.package_name,
        installedVersion=dep.package_version,
        latestVersion=reg.get("latest_version"),
        status=computed_status,
        severity=severity,
        cve=cve,
        license=dep.license or "Unknown",
        outdated=reg.get("outdated"),
        publishedAt=reg.get("published_at"),
        registrySource=reg.get("provider"),
        registryStatus=reg.get("status"),
        weeklyDownloads=0,
        maintainers=0,
        lastPublished="N/A",
        size="N/A",
        description="",
        recommendation="",
        healthScore=0,
        dependents=dependents,
        repository=dep.project.name,
        direct=dep.is_direct
    )


async def get_project_graph(db: AsyncSession, project_id: uuid.UUID) -> GraphResponse:
    """Build a dependency graph from the latest completed scan for the project."""
    # Find the latest completed scan for this project
    scan_stmt = (
        select(Scan)
        .where(Scan.project_id == project_id, Scan.status == ScanStatus.COMPLETED)
        .order_by(Scan.completed_at.desc())
        .limit(1)
    )
    latest_scan = (await db.execute(scan_stmt)).scalar_one_or_none()

    if not latest_scan:
        # No completed scan yet — return empty graph
        return GraphResponse(nodes=[], edges=[])

    # Load all dependencies from this scan
    deps_stmt = (
        select(Dependency)
        .options(selectinload(Dependency.vulnerabilities))
        .where(Dependency.scan_id == latest_scan.id)
        .order_by(Dependency.package_name)
    )
    dependencies = (await db.execute(deps_stmt)).scalars().all()

    if not dependencies:
        return GraphResponse(nodes=[], edges=[])

    # Build a root node for the project
    proj_stmt = select(Project).where(Project.id == project_id)
    project = (await db.execute(proj_stmt)).scalar_one_or_none()
    project_label = project.name if project else "Project"

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    root_node = GraphNode(id="root", label=project_label, status="safe", depth=0, x=0.0, y=0.0)
    nodes.append(root_node)

    # Lay dependency nodes in a circle around the root
    n = len(dependencies)
    radius = max(150.0, n * 25.0)

    for i, dep in enumerate(dependencies):
        angle = (2 * math.pi * i) / n
        x = round(radius * math.cos(angle), 2)
        y = round(radius * math.sin(angle), 2)

        is_vulnerable = len(dep.vulnerabilities) > 0
        node_status = "vulnerable" if is_vulnerable else "safe"

        node = GraphNode(
            id=str(dep.id),
            label=dep.package_name,
            status=node_status,
            depth=1,
            x=x,
            y=y
        )
        nodes.append(node)
        edges.append(GraphEdge(**{"from": "root", "to": str(dep.id)}))

    return GraphResponse(nodes=nodes, edges=edges)

