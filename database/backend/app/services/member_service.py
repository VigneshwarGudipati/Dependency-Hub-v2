"""Member service for mapping user/role relationships."""

import uuid
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import member_repository
from app.schemas.member import MemberResponse


async def get_members(db: AsyncSession, organization_id: uuid.UUID) -> List[MemberResponse]:
    """Fetch active members and map them to the frontend AppUser schema."""
    members_data = await member_repository.find_members(db, organization_id)
    
    responses = []
    for member_assoc, user, role in members_data:
        responses.append(MemberResponse(
            id=user.id,
            name=user.full_name or user.username,
            email=user.email,
            role=role.name,  # Actual resolved role name (e.g. "Admin")
            status=member_assoc.status,
            team="Default",  # Placeholder since no Team model exists
            lastActive=user.last_login_at or user.created_at,
            avatarColor="#" + str(user.id).replace("-", "")[:6]  # Deterministic color based on ID
        ))
    return responses
