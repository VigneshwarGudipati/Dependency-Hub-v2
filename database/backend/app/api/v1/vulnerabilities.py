import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_organization_id, require_permission
from app.schemas.vulnerability import VulnerabilityResponse
from app.schemas.pagination import PaginatedResponse
from app.services import vulnerability_service, project_service

router = APIRouter(prefix="/projects/{project_id}", tags=["Vulnerabilities"])

@router.get(
    "/vulnerabilities",
    response_model=PaginatedResponse[VulnerabilityResponse],
    dependencies=[Depends(require_permission("finding.read"))]
)
async def list_vulnerabilities(
    project_id: uuid.UUID = Path(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    query: Optional[str] = Query(None),
    severity: Optional[str] = Query("all"),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_current_organization_id)
):
    """List vulnerabilities for a specific project."""
    await project_service.get_project(db, project_id, organization_id)
    return await vulnerability_service.list_vulnerabilities(
        db=db,
        organization_id=organization_id,
        page=page,
        page_size=page_size,
        query=query,
        severity=severity,
        project_id=project_id
    )
