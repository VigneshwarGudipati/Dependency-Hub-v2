"""Project service for orchestration, business logic, and mapped responses."""

import uuid
import re
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectStatus, ProjectVisibility, RepositoryProvider, ProjectType
from app.models.audit import AuditLog, AuditAction
from app.repositories import project_repository
from app.schemas.project import ProjectCreate, ProjectResponse


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from a project name."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')


async def get_projects(
    db: AsyncSession,
    organization_id: uuid.UUID,
    search: Optional[str] = None,
    status: Optional[str] = None,
    language: Optional[str] = None,
) -> List[ProjectResponse]:
    """Fetch and map all projects for the given organization."""
    projects = await project_repository.find_projects(db, organization_id, search, status, language)
    
    responses = []
    for p in projects:
        # Note: Since scans are deferred, we fetch safe zeroes.
        stats = await project_repository.get_project_statistics(db, p.id)
        
        # Ensure creator is loaded to display owner fallback, or use organization
        owner = p.creator.username if p.creator else "Organization"
        
        responses.append(ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            language=p.language,
            visibility=p.visibility,
            branch=p.default_branch,
            owner=owner,
            healthScore=stats["healthScore"],
            dependencies=stats["dependencies"],
            vulnerabilities=stats["vulnerabilities"],
            outdated=stats["outdated"],
            lastScan=stats["lastScan"],
            createdAt=p.created_at,
            status=p.status.value.lower().replace("_", "-")  # e.g., "ACTIVE" -> "active", "AT_RISK" -> "at-risk"
        ))
    return responses


async def get_project(
    db: AsyncSession, project_id: uuid.UUID, organization_id: uuid.UUID
) -> ProjectResponse:
    """Fetch and map a single project with tenant isolation."""
    p = await project_repository.find_project_by_id(db, project_id, organization_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    stats = await project_repository.get_project_statistics(db, p.id)
    owner = p.creator.username if p.creator else "Organization"

    return ProjectResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        language=p.language,
        visibility=p.visibility,
        branch=p.default_branch,
        owner=owner,
        healthScore=stats["healthScore"],
        dependencies=stats["dependencies"],
        vulnerabilities=stats["vulnerabilities"],
        outdated=stats["outdated"],
        lastScan=stats["lastScan"],
        createdAt=p.created_at,
        status=p.status.value.lower().replace("_", "-")
    )


async def create_project(
    db: AsyncSession, 
    project_in: ProjectCreate, 
    organization_id: uuid.UUID, 
    user_id: uuid.UUID
) -> ProjectResponse:
    """Create a new project enforcing uniqueness and emitting an audit log."""
    slug = generate_slug(project_in.name)
    
    if await project_repository.check_slug_exists(db, slug, organization_id):
        raise HTTPException(status_code=409, detail="A project with a similar name already exists in this organization")

    project = Project(
        organization_id=organization_id,
        name=project_in.name,
        slug=slug,
        description=project_in.description,
        language=project_in.language,
        visibility=project_in.visibility,
        default_branch=project_in.branch,
        repository_url=project_in.url,
        created_by=user_id,
        status=ProjectStatus.ACTIVE,
        repository_provider=RepositoryProvider.OTHER,
        project_type=ProjectType.OTHER,
    )

    project = await project_repository.create_project(db, project)

    # Emit Audit Log
    audit_log = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        action=AuditAction.PROJECT_CREATED,
        entity_type="project",
        entity_id=str(project.id),
        new_values={"name": project.name, "visibility": project.visibility.value}
    )
    db.add(audit_log)
    await db.commit()

    # The newly created project doesn't have the creator relationship loaded yet, so we pass current user
    # Or we can just re-fetch to ensure all relationships are loaded
    return await get_project(db, project.id, organization_id)
