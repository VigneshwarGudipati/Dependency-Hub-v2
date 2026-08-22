"""Tests for database integrity constraints, unique indexes, and foreign keys."""

import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    Dependency,
    DependencyEdge,
    DependencyType,
    MemberStatus,
    Organization,
    OrganizationMember,
    PackageEcosystem,
    Project,
    ProjectArtifact,
    RefreshToken,
    RelationshipType,
    Role,
    Scan,
    SystemRoleName,
    User,
)


@pytest.mark.asyncio
async def test_duplicate_user_email_rejection(seeded_session: AsyncSession, sample_user: User):
    """Verify that creating a user with an existing email raises IntegrityError."""
    dup_user = User(
        email=sample_user.email,  # duplicate
        username="different_username_123",
        password_hash="some_hash",
    )
    seeded_session.add(dup_user)
    with pytest.raises(IntegrityError):
        await seeded_session.flush()


@pytest.mark.asyncio
async def test_duplicate_org_slug_rejection(seeded_session: AsyncSession, sample_org: Organization):
    """Verify that creating an organization with an existing slug raises IntegrityError."""
    dup_org = Organization(
        name="Another Name",
        slug=sample_org.slug,  # duplicate
    )
    seeded_session.add(dup_org)
    with pytest.raises(IntegrityError):
        await seeded_session.flush()


@pytest.mark.asyncio
async def test_duplicate_membership_rejection(
    seeded_session: AsyncSession,
    sample_org: Organization,
    sample_user: User,
):
    """Verify that duplicate active membership for the same user in an org is rejected."""
    res = await seeded_session.execute(select(Role).where(Role.name == SystemRoleName.DEVELOPER.value))
    dev_role = res.scalar_one()

    # sample_user is already a member (OWNER) in sample_org from conftest
    dup_member = OrganizationMember(
        organization_id=sample_org.id,
        user_id=sample_user.id,
        role_id=dev_role.id,
    )
    seeded_session.add(dup_member)
    with pytest.raises(IntegrityError):
        await seeded_session.flush()


@pytest.mark.asyncio
async def test_duplicate_project_slug_within_same_org_rejection(
    seeded_session: AsyncSession,
    sample_org: Organization,
    sample_project: Project,
):
    """Verify that duplicate project slug within the same org raises IntegrityError."""
    dup_project = Project(
        organization_id=sample_org.id,
        name="Duplicate Name",
        slug=sample_project.slug,  # duplicate slug in same org
    )
    seeded_session.add(dup_project)
    with pytest.raises(IntegrityError):
        await seeded_session.flush()


@pytest.mark.asyncio
async def test_same_project_slug_in_different_orgs_allowed(
    seeded_session: AsyncSession,
    sample_user: User,
    sample_project: Project,
):
    """Verify that identical project slug in a DIFFERENT org is allowed."""
    other_org = Organization(
        name="Beta Industries",
        slug=f"beta-{uuid.uuid4().hex[:8]}",
    )
    seeded_session.add(other_org)
    await seeded_session.flush()

    other_project = Project(
        organization_id=other_org.id,
        name="Another Payment Gateway",
        slug=sample_project.slug,  # same slug, different org
        created_by=sample_user.id,
    )
    seeded_session.add(other_project)
    await seeded_session.flush()
    assert other_project.id is not None


@pytest.mark.asyncio
async def test_dependency_uniqueness_within_scan(
    seeded_session: AsyncSession,
    sample_project: Project,
    sample_user: User,
):
    """Verify that duplicate (scan_id, ecosystem_id, package_name, package_version) is rejected."""
    artifact = ProjectArtifact(
        project_id=sample_project.id,
        version_number=1,
        original_filename="app.zip",
        storage_key="k1",
        content_hash="h1",
    )
    seeded_session.add(artifact)
    await seeded_session.flush()

    scan = Scan(
        project_id=sample_project.id,
        artifact_id=artifact.id,
    )
    seeded_session.add(scan)
    await seeded_session.flush()

    res = await seeded_session.execute(select(PackageEcosystem).where(PackageEcosystem.name == "PyPI"))
    pypi = res.scalar_one()

    dep1 = Dependency(
        project_id=sample_project.id,
        scan_id=scan.id,
        ecosystem_id=pypi.id,
        package_name="requests",
        package_version="2.31.0",
    )
    seeded_session.add(dep1)
    await seeded_session.flush()

    dep2 = Dependency(
        project_id=sample_project.id,
        scan_id=scan.id,
        ecosystem_id=pypi.id,
        package_name="requests",
        package_version="2.31.0",  # duplicate in same scan
    )
    seeded_session.add(dep2)
    with pytest.raises(IntegrityError):
        await seeded_session.flush()


@pytest.mark.asyncio
async def test_foreign_key_violation_rejection(seeded_session: AsyncSession):
    """Verify that referencing a non-existent foreign key raises IntegrityError."""
    fake_id = uuid.uuid4()
    project = Project(
        organization_id=fake_id,  # non-existent organization
        name="Ghost Project",
        slug="ghost",
    )
    seeded_session.add(project)
    with pytest.raises(IntegrityError):
        await seeded_session.flush()
