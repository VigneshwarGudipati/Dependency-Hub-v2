"""Pytest configuration and async fixtures for Dependency Hub database testing."""

import uuid
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import select

from app.core.config import settings
from app.core.seeds import seed_reference_data
from app.models import (
    Base,
    Organization,
    OrganizationMember,
    Project,
    ProjectArtifact,
    Role,
    Scan,
    SystemRoleName,
    User,
)


@pytest.fixture(autouse=True)
def cleanup_test_artifacts():
    """Ensure artifacts created during the test are removed."""
    from pathlib import Path
    storage_dir = Path(settings.STORAGE_DIR)

    # Snapshot before test
    files_before = set()
    if storage_dir.exists():
        files_before = {f for f in storage_dir.rglob('*') if f.is_file()}

    yield

    # Cleanup after test
    if storage_dir.exists():
        files_after = {f for f in storage_dir.rglob('*') if f.is_file()}
        new_files = files_after - files_before
        for new_file in new_files:
            try:
                new_file.unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                # Cleanup failures must not be silently swallowed
                raise RuntimeError(f"Failed to cleanup test storage file {new_file}") from e

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a clean async engine with NullPool per test."""
    engine = create_async_engine(
        settings.async_database_url,
        poolclass=NullPool,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session for each test with savepoints and rollback."""
    async with test_engine.connect() as connection:
        trans = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            if trans.is_active:
                await trans.rollback()


@pytest_asyncio.fixture(scope="function")
async def seeded_session(db_session: AsyncSession) -> AsyncSession:
    """Session with baseline reference roles, permissions, ecosystems, and licenses seeded."""
    await seed_reference_data(db_session)
    return db_session


@pytest_asyncio.fixture
async def sample_user(seeded_session: AsyncSession) -> User:
    """Fixture providing a standard test user."""
    user = User(
        email=f"user_{uuid.uuid4().hex[:8]}@example.com",
        username=f"testuser_{uuid.uuid4().hex[:8]}",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$dummyhashvaluefortestingpurposesonly",
        full_name="Test Developer",
        is_active=True,
        is_verified=True,
    )
    seeded_session.add(user)
    await seeded_session.flush()
    return user


@pytest_asyncio.fixture
async def sample_org(seeded_session: AsyncSession, sample_user: User) -> Organization:
    """Fixture providing a standard test organization with sample_user as OWNER."""
    org = Organization(
        name="Acme Corp",
        slug=f"acme-{uuid.uuid4().hex[:8]}",
        description="Acme Corporation Workspace",
        is_active=True,
    )
    seeded_session.add(org)
    await seeded_session.flush()

    # Fetch Owner role
    res = await seeded_session.execute(select(Role).where(Role.name == SystemRoleName.OWNER.value))
    owner_role = res.scalar_one()

    member = OrganizationMember(
        organization_id=org.id,
        user_id=sample_user.id,
        role_id=owner_role.id,
    )
    seeded_session.add(member)
    await seeded_session.flush()

    return org


@pytest_asyncio.fixture
async def sample_project(seeded_session: AsyncSession, sample_org: Organization, sample_user: User) -> Project:
    """Fixture providing a standard test project."""
    project = Project(
        organization_id=sample_org.id,
        name="Payment Gateway API",
        slug="payment-gateway",
        description="Core payments processing service",
        repository_url="https://github.com/acme/payment-gateway",
        created_by=sample_user.id,
    )
    seeded_session.add(project)
    await seeded_session.flush()
    return project
