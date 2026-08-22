"""Authentication API router."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _client_ip(request: Request) -> str:
    """Extract client IP from the request."""
    return request.client.host if request.client else "unknown"


def _user_agent(request: Request) -> str:
    """Extract User-Agent header."""
    return request.headers.get("user-agent", "unknown")[:500]


def _request_id(request: Request) -> str:
    """Extract the request ID from state."""
    return getattr(request.state, "request_id", "unknown")


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account with organization."""
    return await auth_service.register(
        request=body,
        db=db,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        request_id=_request_id(request),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and receive a token pair."""
    return await auth_service.login(
        request=body,
        db=db,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        request_id=_request_id(request),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Rotate refresh token and receive a new token pair."""
    return await auth_service.refresh(
        request=body,
        db=db,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        request_id=_request_id(request),
    )


@router.post("/logout", status_code=204)
async def logout(
    body: LogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revoke the refresh token and log out."""
    await auth_service.logout(
        request=body,
        db=db,
        request_id=_request_id(request),
        user_id=user.id,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current authenticated user's profile."""
    return await auth_service.get_me(user, db)
