"""Tests for multi-tenant data isolation and membership scoping."""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Finding,
    FindingSeverity,
    FindingType,
    Organization,
    OrganizationMember,
    Project,
    ProjectArtifact,
    Role,
    Scan,
    SecurityPolicy,
    SystemRoleName,
    User,
)


@pytest.mark.asyncio
async def test_tenant_boundary_isolation(seeded_session: AsyncSession):
    """Verify that Organization A and Organization B data hierarchies remain strictly segregated."""
    # 1. Fetch OWNER role
    res = await seeded_session.execute(select(Role).where(Role.name == SystemRoleName.OWNER.value))
    owner_role = res.scalar_one()

    # 2. Setup Tenant A
    user_a = User(
        email=f"alice_{uuid.uuid4().hex[:6]}@org-a.com",
        username=f"alice_{uuid.uuid4().hex[:6]}",
        password_hash="hash_a",
    )
    seeded_session.add(user_a)
    await seeded_session.flush()

    org_a = Organization(
        name="Tenant Alpha",
        slug=f"tenant-alpha-{uuid.uuid4().hex[:6]}",
    )
    seeded_session.add(org_a)
    await seeded_session.flush()

    seeded_session.add(OrganizationMember(
        organization_id=org_a.id,
        user_id=user_a.id,
        role_id=owner_role.id,
    ))

    project_a = Project(
        organization_id=org_a.id,
        name="Alpha Service",
        slug="alpha-service",
        created_by=user_a.id,
    )
    seeded_session.add(project_a)
    await seeded_session.flush()

    policy_a = SecurityPolicy(
        organization_id=org_a.id,
        name="Alpha Security Rules",
        configuration={"rule": "strict"},
        created_by=user_a.id,
    )
    seeded_session.add(policy_a)

    # 3. Setup Tenant B
    user_b = User(
        email=f"bob_{uuid.uuid4().hex[:6]}@org-b.com",
        username=f"bob_{uuid.uuid4().hex[:6]}",
        password_hash="hash_b",
    )
    seeded_session.add(user_b)
    await seeded_session.flush()

    org_b = Organization(
        name="Tenant Beta",
        slug=f"tenant-beta-{uuid.uuid4().hex[:6]}",
    )
    seeded_session.add(org_b)
    await seeded_session.flush()

    seeded_session.add(OrganizationMember(
        organization_id=org_b.id,
        user_id=user_b.id,
        role_id=owner_role.id,
    ))

    project_b = Project(
        organization_id=org_b.id,
        name="Beta Service",
        slug="beta-service",
        created_by=user_b.id,
    )
    seeded_session.add(project_b)
    await seeded_session.flush()

    policy_b = SecurityPolicy(
        organization_id=org_b.id,
        name="Beta Security Rules",
        configuration={"rule": "permissive"},
        created_by=user_b.id,
    )
    seeded_session.add(policy_b)
    await seeded_session.flush()

    # 4. Query Scoping for Tenant A
    stmt_org_a_projects = select(Project).where(Project.organization_id == org_a.id)
    res_a_proj = await seeded_session.execute(stmt_org_a_projects)
    org_a_projects = res_a_proj.scalars().all()

    assert len(org_a_projects) == 1
    assert org_a_projects[0].name == "Alpha Service"
    assert org_a_projects[0].organization_id == org_a.id

    # 5. Query Scoping for Tenant B
    stmt_org_b_policies = select(SecurityPolicy).where(SecurityPolicy.organization_id == org_b.id)
    res_b_pol = await seeded_session.execute(stmt_org_b_policies)
    org_b_policies = res_b_pol.scalars().all()

    assert len(org_b_policies) == 1
    assert org_b_policies[0].name == "Beta Security Rules"
    assert org_b_policies[0].configuration["rule"] == "permissive"

    # 6. Verify User A has NO membership in Org B
    stmt_user_a_in_b = select(OrganizationMember).where(
        OrganizationMember.organization_id == org_b.id,
        OrganizationMember.user_id == user_a.id,
    )
    res_user_a_b = await seeded_session.execute(stmt_user_a_in_b)
    assert res_user_a_b.scalar_one_or_none() is None
