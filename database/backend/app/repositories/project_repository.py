"""Project repository for tenant-scoped CRUD operations and statistics."""

import uuid
from typing import List, Optional, Tuple, Any, Dict

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project, ProjectStatus
from app.models.user import User


async def find_projects(
    db: AsyncSession,
    organization_id: uuid.UUID,
    search: Optional[str] = None,
    status: Optional[str] = None,
    language: Optional[str] = None,
) -> List[Project]:
    """Retrieve all projects for a given organization, matching optional filters."""
    stmt = select(Project).where(Project.organization_id == organization_id, Project.deleted_at.is_(None))

    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.outerjoin(User, Project.created_by == User.id).where(
            or_(
                Project.name.ilike(search_pattern),
                Project.description.ilike(search_pattern),
                User.username.ilike(search_pattern),
            )
        )
    else:
        # Load creator to avoid N+1 if we don't join above
        stmt = stmt.options(selectinload(Project.creator))

    if status and status != "all":
        try:
            enum_status = ProjectStatus[status.upper().replace("-", "_")]
            stmt = stmt.where(Project.status == enum_status)
        except KeyError:
            pass  # Ignore invalid status filter

    if language and language != "all":
        stmt = stmt.where(Project.language.ilike(language))

    stmt = stmt.order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def find_project_by_id(
    db: AsyncSession, project_id: uuid.UUID, organization_id: uuid.UUID
) -> Optional[Project]:
    """Fetch a specific project ensuring tenant isolation."""
    stmt = (
        select(Project)
        .options(selectinload(Project.creator))
        .where(
            Project.id == project_id,
            Project.organization_id == organization_id,
            Project.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def check_slug_exists(
    db: AsyncSession, slug: str, organization_id: uuid.UUID
) -> bool:
    """Check if a project slug is already taken within the organization."""
    stmt = select(Project.id).where(
        Project.slug == slug,
        Project.organization_id == organization_id,
        Project.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    return result.first() is not None


async def create_project(db: AsyncSession, project: Project) -> Project:
    """Persist a new project to the database."""
    db.add(project)
    await db.flush()
    return project


async def get_project_statistics(db: AsyncSession, project_id: uuid.UUID) -> Dict[str, Any]:
    """Retrieve aggregated health statistics for a project.
    Note: Phase 4 defers actual scanning, so these are currently mocked/defaulted 
    as safe empty/zero values as per constraints.
    """
    # In Phase 5/6, this will do actual aggregates over vulnerabilities/dependencies tables.
    return {
        "healthScore": 100,  # No scans yet
        "dependencies": 0,
        "vulnerabilities": 0,
        "outdated": 0,
        "lastScan": None,
    }
