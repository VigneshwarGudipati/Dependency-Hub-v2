"""Authentication service: registration, login, token management, logout."""

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token_value,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.audit import AuditAction, AuditLog
from app.models.role import Role
from app.repositories import (
    membership_repository,
    refresh_token_repository,
    user_repository,
)
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    OrganizationInfo,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger("dependencyhub.auth")


def _generate_username(email: str) -> str:
    """Derive a username from the email local part, lowercased and sanitized."""
    local = email.split("@")[0].lower()
    # Keep only alphanumeric and hyphens/underscores
    return re.sub(r"[^a-z0-9_\-]", "", local) or "user"


async def _ensure_unique_username(db: AsyncSession, base: str) -> str:
    """Append a numeric suffix if the base username is taken."""
    candidate = base
    suffix = 0
    while True:
        existing = await user_repository.find_by_username(db, candidate)
        if not existing:
            return candidate
        suffix += 1
        candidate = f"{base}{suffix}"


def _generate_org_slug(company: str, user_id: uuid.UUID) -> str:
    """Generate a URL-safe slug from the company name."""
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    if not slug:
        slug = "org"
    # Append short UUID suffix for uniqueness
    return f"{slug}-{str(user_id)[:8]}"


async def _build_user_response(
    db: AsyncSession, user, membership=None
) -> UserResponse:
    """Build a UserResponse from a User model and optional membership."""
    org_info = None
    role_name = None
    if membership is None:
        memberships = await membership_repository.find_active_memberships(db, user.id)
        membership = memberships[0] if memberships else None
    if membership:
        org = membership.organization
        org_info = OrganizationInfo(id=org.id, name=org.name, slug=org.slug)
        role_name = membership.role.name if membership.role else None
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        organization=org_info,
        role=role_name,
    )


async def _create_audit_log(
    db: AsyncSession,
    action: AuditAction,
    user_id: Optional[uuid.UUID],
    organization_id: Optional[uuid.UUID],
    entity_type: str,
    entity_id: Optional[str],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Create an audit log entry for supported actions."""
    log = AuditLog(
        action=action,
        user_id=user_id,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        audit_metadata=metadata or {},
    )
    db.add(log)
    await db.flush()


async def _issue_token_pair(
    db: AsyncSession,
    user,
    membership,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> TokenResponse:
    """Generate access + refresh tokens and persist the refresh token hash."""
    access_token = create_access_token(subject=str(user.id))
    raw_refresh = create_refresh_token_value()
    refresh_hash = hash_refresh_token(raw_refresh)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    await refresh_token_repository.create(
        db,
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    user_response = await _build_user_response(db, user, membership)

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        user=user_response,
    )


# --- Public API ---

async def register(
    request: RegisterRequest,
    db: AsyncSession,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
) -> TokenResponse:
    """Register a new user with organization and membership (atomic)."""
    # Check duplicate email
    existing = await user_repository.find_by_email(db, request.email)
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    # Create user
    base_username = _generate_username(request.email)
    username = await _ensure_unique_username(db, base_username)
    pw_hash = hash_password(request.password)
    user = await user_repository.create_user(
        db,
        email=request.email,
        username=username,
        password_hash=pw_hash,
        full_name=request.name,
    )

    # Resolve OWNER role from seeded data
    stmt = select(Role).where(Role.name == "OWNER")
    result = await db.execute(stmt)
    owner_role = result.scalar_one_or_none()
    if not owner_role:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="System roles not initialized")

    # Create organization
    company_name = request.company.strip() if request.company else f"{request.name}'s Organization"
    slug = _generate_org_slug(company_name, user.id)
    org = await membership_repository.create_organization(db, name=company_name, slug=slug)

    # Create membership
    membership = await membership_repository.create_membership(
        db, organization_id=org.id, user_id=user.id, role_id=owner_role.id
    )

    # Issue tokens
    token_response = await _issue_token_pair(db, user, membership, ip_address, user_agent)

    await db.commit()

    logger.info(f"User registered: email={request.email} org={slug} [req_id={request_id}]")
    return token_response


async def login(
    request: LoginRequest,
    db: AsyncSession,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
) -> TokenResponse:
    """Authenticate a user and return a token pair."""
    from fastapi import HTTPException

    user = await user_repository.find_by_email(db, request.email)
    if not user or not verify_password(request.password, user.password_hash):
        logger.warning(f"Login failed: email={request.email} [req_id={request_id}]")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        logger.warning(f"Login blocked (inactive): email={request.email} [req_id={request_id}]")
        raise HTTPException(status_code=401, detail="Account is disabled")

    # Resolve membership
    memberships = await membership_repository.find_active_memberships(db, user.id)
    membership = memberships[0] if memberships else None

    # Update last login
    await user_repository.update_last_login(db, user)

    # Issue tokens
    token_response = await _issue_token_pair(db, user, membership, ip_address, user_agent)

    # Audit login
    org_id = membership.organization_id if membership else None
    await _create_audit_log(
        db,
        action=AuditAction.USER_LOGIN,
        user_id=user.id,
        organization_id=org_id,
        entity_type="user",
        entity_id=str(user.id),
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        metadata={"email": user.email},
    )

    await db.commit()

    logger.info(f"User logged in: email={user.email} [req_id={request_id}]")
    return token_response


async def refresh(
    request: RefreshRequest,
    db: AsyncSession,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
) -> TokenResponse:
    """Rotate a refresh token: revoke old, issue new pair."""
    from fastapi import HTTPException

    token_hash = hash_refresh_token(request.refresh_token)
    token_record = await refresh_token_repository.find_by_hash(db, token_hash)

    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if token_record.revoked_at is not None:
        # Potential reuse: revoke ALL tokens for this user as a security measure
        await refresh_token_repository.revoke_all_for_user(db, token_record.user_id)
        await db.commit()
        logger.warning(
            f"Refresh token reuse detected: user_id={token_record.user_id} [req_id={request_id}]"
        )
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    if token_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token has expired")

    # Revoke old token
    await refresh_token_repository.revoke(db, token_record)

    # Load user
    user = await user_repository.find_by_id(db, token_record.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    memberships = await membership_repository.find_active_memberships(db, user.id)
    membership = memberships[0] if memberships else None
    token_response = await _issue_token_pair(db, user, membership, ip_address, user_agent)

    await db.commit()

    logger.info(f"Token refreshed: user_id={user.id} [req_id={request_id}]")
    return token_response


async def logout(
    request: LogoutRequest,
    db: AsyncSession,
    request_id: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Revoke a refresh token on logout."""
    token_hash = hash_refresh_token(request.refresh_token)
    token_record = await refresh_token_repository.find_by_hash(db, token_hash)

    if token_record and token_record.revoked_at is None:
        await refresh_token_repository.revoke(db, token_record)

        # Audit logout
        memberships = await membership_repository.find_active_memberships(db, token_record.user_id)
        membership = memberships[0] if memberships else None
        org_id = membership.organization_id if membership else None
        await _create_audit_log(
            db,
            action=AuditAction.USER_LOGOUT,
            user_id=token_record.user_id,
            organization_id=org_id,
            entity_type="user",
            entity_id=str(token_record.user_id),
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

        await db.commit()
        logger.info(f"User logged out: user_id={token_record.user_id} [req_id={request_id}]")


async def get_me(user, db: AsyncSession) -> UserResponse:
    """Return current user profile with organization info."""
    return await _build_user_response(db, user)
