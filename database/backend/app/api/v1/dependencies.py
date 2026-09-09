import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_organization_id, require_permission
from app.schemas.dependency import DependencyPackage
from app.schemas.pagination import PaginatedResponse
from app.services import dependency_service, project_service

router = APIRouter(prefix="/projects/{project_id}", tags=["Dependencies"])

@router.get(
    "/dependencies",
    response_model=PaginatedResponse[DependencyPackage],
    dependencies=[Depends(require_permission("dependency.read"))]
)
async def list_dependencies(
    project_id: uuid.UUID = Path(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    query: Optional[str] = Query(None),
    status: Optional[str] = Query("all"),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_current_organization_id)
):
    """List dependencies for a specific project."""
    await project_service.get_project(db, project_id, organization_id)
    return await dependency_service.list_dependencies(
        db=db,
        organization_id=organization_id,
        page=page,
        page_size=page_size,
        query=query,
        status=status,
        project_id=project_id
    )

@router.get(
    "/dependencies/{dependency_id}",
    response_model=DependencyPackage,
    dependencies=[Depends(require_permission("dependency.read"))]
)
async def get_dependency(
    project_id: uuid.UUID = Path(...),
    dependency_id: uuid.UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_current_organization_id)
):
    """Get dependency details."""
    await project_service.get_project(db, project_id, organization_id)
    dep = await dependency_service.get_dependency_detail(db, organization_id, project_id, dependency_id)
    if not dep:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Dependency not found")
    return dep
