"""Dashboard API router."""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_organization_id, require_permission
from app.schemas.dashboard import DashboardSummary
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get(
    "/summary",
    response_model=DashboardSummary,
    dependencies=[Depends(require_permission("project.read"))]
)
async def get_dashboard_summary(
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """Get the dashboard summary metrics."""
    return await dashboard_service.get_dashboard_summary(db, organization_id)
