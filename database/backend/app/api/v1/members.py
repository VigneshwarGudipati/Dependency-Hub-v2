"""Members API router."""

import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.dependencies import get_db, get_current_user, get_current_organization_id, require_permission
from app.schemas.member import MemberResponse
from app.services import member_service


router = APIRouter(prefix="/members", tags=["Members"])


@router.get(
    "",
    response_model=List[MemberResponse],
    dependencies=[Depends(require_permission("member.read"))]
)
async def list_members(
    organization_id: uuid.UUID = Depends(get_current_organization_id),
    db: AsyncSession = Depends(get_db)
):
    """List all active members for the authenticated user's current organization."""
    return await member_service.get_members(db, organization_id)
