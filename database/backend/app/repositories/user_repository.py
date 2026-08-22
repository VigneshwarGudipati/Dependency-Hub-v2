"""User repository for database access operations."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def find_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Find a user by email (case-insensitive)."""
    stmt = select(User).where(User.email == email.lower().strip())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Find a user by primary key."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Find a user by username."""
    stmt = select(User).where(User.username == username.lower().strip())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    username: str,
    password_hash: str,
    full_name: Optional[str] = None,
) -> User:
    """Create a new user record."""
    user = User(
        email=email.lower().strip(),
        username=username.lower().strip(),
        password_hash=password_hash,
        full_name=full_name,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()
    return user


async def update_last_login(db: AsyncSession, user: User) -> None:
    """Update the user's last_login_at timestamp."""
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
