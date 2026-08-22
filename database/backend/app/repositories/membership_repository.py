"""Organization membership repository for RBAC resolution."""

import uuid
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrganizationMember, MemberStatus
from app.models.role import Role
from app.models.permission import Permission, RolePermission


async def find_membership(
    db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID
) -> Optional[OrganizationMember]:
    """Find an active membership for user in a specific organization."""
    stmt = (
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.organization), selectinload(OrganizationMember.role))
        .where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == org_id,
            OrganizationMember.status == MemberStatus.ACTIVE,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_active_memberships(
    db: AsyncSession, user_id: uuid.UUID
) -> List[OrganizationMember]:
    """Find all active memberships for a user."""
    stmt = (
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.organization), selectinload(OrganizationMember.role))
        .where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == MemberStatus.ACTIVE,
        )
        .order_by(OrganizationMember.joined_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_permissions_for_role(db: AsyncSession, role_id: uuid.UUID) -> List[str]:
    """Resolve permission codes for a given role."""
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_organization(db: AsyncSession, name: str, slug: str) -> Organization:
    """Create a new organization."""
    org = Organization(name=name, slug=slug, is_active=True)
    db.add(org)
    await db.flush()
    return org


async def create_membership(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
) -> OrganizationMember:
    """Create a new organization membership."""
    member = OrganizationMember(
        organization_id=organization_id,
        user_id=user_id,
        role_id=role_id,
        status=MemberStatus.ACTIVE,
    )
    db.add(member)
    await db.flush()
    return member
