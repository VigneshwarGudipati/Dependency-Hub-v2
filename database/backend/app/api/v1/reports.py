"""Reports API router."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, get_current_organization_id, require_permission
from app.schemas.report import ReportCreate, ReportResponse, ReportDetailResponse
from app.services.reporting import report_service
from app.services import project_service
from app.models.user import User


router = APIRouter(prefix="/projects/{project_id}/reports", tags=["Reports"])

async def verify_project_access(
    project_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    await project_service.get_project(db, project_id, organization_id)
    return project_id


@router.post(
    "",
    response_model=ReportResponse,
    status_code=201,
    dependencies=[Depends(require_permission("report.create")), Depends(verify_project_access)]
)
async def create_report(
    project_id: uuid.UUID,
    report_in: ReportCreate,
    user: User = Depends(get_current_user),
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Idempotently create a new report for a project."""
    return await report_service.create_report(db, project_id, organization_id, user.id, report_in)


@router.post(
    "/{report_id}/retry",
    response_model=ReportResponse,
    status_code=200,
    dependencies=[Depends(require_permission("report.retry")), Depends(verify_project_access)]
)
async def retry_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Retry a FAILED report."""
    return await report_service.retry_report(db, report_id, project_id, organization_id, user.id)


@router.get(
    "",
    response_model=List[ReportResponse],
    dependencies=[Depends(require_permission("report.read")), Depends(verify_project_access)]
)
async def list_reports(
    project_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by report status"),
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    format: Optional[str] = Query(None, description="Filter by report format"),
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """List reports in a project with optional filtering."""
    return await report_service.list_reports(db, project_id, organization_id, skip, limit, status, report_type, format)


@router.get(
    "/{report_id}",
    response_model=ReportDetailResponse,
    dependencies=[Depends(require_permission("report.read")), Depends(verify_project_access)]
)
async def get_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve detailed information about a report."""
    return await report_service.get_report_or_404(db, report_id, organization_id, project_id)


@router.get(
    "/{report_id}/download",
    dependencies=[Depends(require_permission("report.download")), Depends(verify_project_access)]
)
async def download_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Download a completed report artifact."""
    plaintext, filename, content_type = await report_service.download_report(db, report_id, project_id, organization_id, user.id)
    return Response(content=plaintext, media_type=content_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    })


@router.delete(
    "/{report_id}",
    status_code=204,
    dependencies=[Depends(require_permission("report.delete")), Depends(verify_project_access)]
)
async def delete_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Delete a report."""
    await report_service.delete_report(db, report_id, project_id, organization_id, user.id)
