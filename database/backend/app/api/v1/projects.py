"""Projects API router."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, get_current_organization_id, require_permission
from app.schemas.project import ProjectCreate, ProjectResponse
from app.schemas.artifact import ArtifactResponse
from app.schemas.scan import ScanCreate, ScanResponse
from app.schemas.graph import GraphResponse
from app.services import project_service, artifact_service, scan_service, dependency_service
from app.models.user import User
from fastapi import UploadFile, File, Form, BackgroundTasks


router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get(
    "",
    response_model=List[ProjectResponse],
    dependencies=[Depends(require_permission("project.read"))]
)
async def list_projects(
    search: Optional[str] = Query(None, description="Search term for name/description"),
    status: Optional[str] = Query("all", description="Filter by status (all, healthy, at-risk, critical)"),
    language: Optional[str] = Query("all", description="Filter by language"),
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """List all projects in the current organization with optional filtering."""
    return await project_service.get_projects(db, organization_id, search, status, language)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=201,
    dependencies=[Depends(require_permission("project.create"))]
)
async def create_project(
    project_in: ProjectCreate,
    user: User = Depends(get_current_user),
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Create a new project within the current organization."""
    return await project_service.create_project(db, project_in, organization_id, user.id)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_permission("project.read"))]
)
async def get_project(
    project_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a specific project's details and statistics."""
    return await project_service.get_project(db, project_id, organization_id)


@router.post(
    "/{project_id}/artifacts",
    response_model=ArtifactResponse,
    status_code=201,
    dependencies=[Depends(require_permission("project.upload"))]
)
async def upload_artifact(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    filename: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Upload a new artifact for the project."""
    # Ensure project belongs to current organization
    await project_service.get_project(db, project_id, organization_id)
    
    final_filename = filename or file.filename or "artifact"
    return await artifact_service.create_artifact(db, project_id, user.id, file, final_filename)


@router.post(
    "/{project_id}/scans",
    response_model=ScanResponse,
    status_code=201,
    dependencies=[Depends(require_permission("scan.create"))]
)
async def create_scan(
    project_id: uuid.UUID,
    scan_in: ScanCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Trigger a new scan for a project artifact."""
    await project_service.get_project(db, project_id, organization_id)
    return await scan_service.create_scan(db, project_id, user.id, scan_in, background_tasks)


@router.get(
    "/{project_id}/scans/{scan_id}",
    response_model=ScanResponse,
    dependencies=[Depends(require_permission("scan.read"))]
)
async def get_scan(
    project_id: uuid.UUID,
    scan_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Get the status and details of a specific scan."""
    await project_service.get_project(db, project_id, organization_id)
    return await scan_service.get_scan(db, project_id, scan_id)


@router.get(
    "/{project_id}/graph",
    response_model=GraphResponse,
    dependencies=[Depends(require_permission("dependency.read"))]
)
async def get_project_graph(
    project_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Get the latest dependency graph for the project."""
    await project_service.get_project(db, project_id, organization_id)
    return await dependency_service.get_project_graph(db, project_id)


