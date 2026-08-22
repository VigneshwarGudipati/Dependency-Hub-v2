"""Member repository for tenant-scoped user listing."""

import uuid
from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import OrganizationMember, MemberStatus
from app.models.user import User
from app.models.role import Role


async def find_members(
    db: AsyncSession, organization_id: uuid.UUID
) -> List[Tuple[OrganizationMember, User, Role]]:
    """Retrieve all active members in the given organization with their user and role data."""
    stmt = (
        select(OrganizationMember, User, Role)
        .join(User, OrganizationMember.user_id == User.id)
        .join(Role, OrganizationMember.role_id == Role.id)
        .where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.status == MemberStatus.ACTIVE,
            User.is_active == True,
            User.deleted_at.is_(None)
        )
        .order_by(User.username.asc())
    )
    result = await db.execute(stmt)
    return list(result.all())
