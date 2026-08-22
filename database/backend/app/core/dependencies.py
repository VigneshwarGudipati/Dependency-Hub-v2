"""Reusable FastAPI dependencies for authentication, RBAC, and tenant isolation."""

import uuid
import logging
from typing import Optional, Callable

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token
from app.models.organization import OrganizationMember
from app.models.user import User
from app.repositories import membership_repository, user_repository

logger = logging.getLogger("dependencyhub.auth")

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db(request: Request):
    """Yield an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the bearer token, returning the authenticated User."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await user_repository.find_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    return user


async def get_current_membership(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    """Resolve the current user's active organization membership.
    If exactly one active membership exists, use it. If multiple exist, raise 400 since the frontend
    currently does not pass an explicit active organization context.
    """
    memberships = await membership_repository.find_active_memberships(db, user.id)
    if not memberships:
        raise HTTPException(status_code=403, detail="No active organization membership")
    if len(memberships) > 1:
        # DESIGN CONSTRAINT: Multi-organization not supported by frontend currently.
        raise HTTPException(
            status_code=400, 
            detail="Multiple active organizations found. Explicit organization context is required."
        )
    return memberships[0]


async def get_current_organization_id(
    membership: OrganizationMember = Depends(get_current_membership),
) -> uuid.UUID:
    """Return the current user's active organization ID."""
    return membership.organization_id


def require_permission(permission_code: str) -> Callable:
    """Factory that creates a dependency enforcing a specific permission.

    Usage:
        @router.get("/some-endpoint", dependencies=[Depends(require_permission("project.read"))])
    """
    async def _check_permission(
        membership: OrganizationMember = Depends(get_current_membership),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        permissions = await membership_repository.get_permissions_for_role(db, membership.role_id)
        if permission_code not in permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission_code} required",
            )

    return _check_permission


def require_organization_access(org_id_param: str = "organization_id") -> Callable:
    """Factory that creates a dependency verifying access to a specific organization.

    The organization ID is extracted from the path parameter specified by org_id_param.
    """
    async def _check_access(
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> OrganizationMember:
        org_id_str = request.path_params.get(org_id_param)
        if not org_id_str:
            raise HTTPException(status_code=400, detail="Organization ID required")
        try:
            org_id = uuid.UUID(org_id_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid organization ID")

        membership = await membership_repository.find_membership(db, user.id, org_id)
        if not membership:
            raise HTTPException(status_code=403, detail="Organization access denied")
        return membership

    return _check_access
