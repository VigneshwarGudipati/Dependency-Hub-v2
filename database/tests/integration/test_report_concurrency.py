import asyncio
import uuid
import pytest
from httpx import AsyncClient
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.core.dependencies import get_db
from app.models.report import Report
from app.services.reporting import report_service
from app.schemas.report import ReportCreate
from app.models.organization import Organization, OrganizationMember
from app.models.project import Project, ProjectStatus
from app.models.scan import Scan, ScanStatus, ScanType
from app.models.user import User
from app.models.role import Role, SystemRoleName
from app.models.artifact import ProjectArtifact, ArtifactUploadStatus
import jwt
from datetime import timedelta
from app.core.config import settings
from app.models.base import utc_now

def get_token(user_id: uuid.UUID) -> str:
    from app.core.security import create_access_token
    return create_access_token(str(user_id))
from app.core.seeds import seed_reference_data

@pytest.mark.asyncio
async def test_true_api_concurrent_idempotency(test_engine):
    org_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    async with test_engine.connect() as conn:
        session = AsyncSession(bind=conn)
        await seed_reference_data(session)
        user = User(id=admin_id, email=f'admin_{admin_id}@example.com', username=f'admin_{admin_id}', password_hash='x', is_active=True)
        org = Organization(id=org_id, name='Org', slug=f'org-{org_id}')
        stmt = select(Role).where(Role.name == SystemRoleName.ADMIN)
        admin_role = (await session.execute(stmt)).scalar_one()
        member = OrganizationMember(organization_id=org_id, user_id=admin_id, role_id=admin_role.id)
        proj = Project(id=proj_id, organization_id=org_id, name='Proj', slug=f'proj-{proj_id}', status=ProjectStatus.ACTIVE)
        art_id = uuid.uuid4()
        part = ProjectArtifact(id=art_id, project_id=proj_id, original_filename='x', content_hash='z', size_bytes=1, storage_key='w', upload_status=ArtifactUploadStatus.READY)
        scan = Scan(id=scan_id, project_id=proj_id, artifact_id=art_id, scan_type=ScanType.SECURITY, status=ScanStatus.COMPLETED)

        session.add_all([user, org, member, proj, part, scan])
        await session.commit()
        await session.close()

    token = get_token(admin_id)
    headers = {'Authorization': f'Bearer {token}'}

    payload = {
        'scan_id': str(scan_id),
        'report_type': 'SECURITY_REPORT',
        'format': 'JSON'
    }

    active_requests = 0
    max_active_requests = 0

    async def override_get_db():
        nonlocal active_requests, max_active_requests
        active_requests += 1
        if active_requests > max_active_requests:
            max_active_requests = active_requests
        await asyncio.sleep(0.05) # ensure overlap

        async with test_engine.connect() as conn:
            session = AsyncSession(bind=conn, expire_on_commit=False, autoflush=False)
            try:
                yield session
            finally:
                await session.close()
                active_requests -= 1

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            tasks = [
                client.post(f'/api/v1/projects/{proj_id}/reports', json=payload, headers=headers)
                for _ in range(10)
            ]
            responses = await asyncio.gather(*tasks)

            report_ids = set()
            for resp in responses:
                assert resp.status_code in (201, 200), f'Unexpected status: {resp.status_code} {resp.text}'
                data = resp.json()
                assert data['status'] == 'QUEUED'
                report_ids.add(data['id'])

            assert len(report_ids) == 1
            assert max_active_requests == 10, f"Expected 10 concurrent requests, but got {max_active_requests}"

            async with test_engine.connect() as conn:
                session = AsyncSession(bind=conn)
                stmt = select(Report).where(
                    Report.project_id == proj_id,
                    Report.scan_id == scan_id,
                    Report.report_type == 'SECURITY_REPORT',
                    Report.format == 'JSON'
                )
                reports = (await session.execute(stmt)).scalars().all()
                assert len(reports) == 1
                assert str(reports[0].id) == list(report_ids)[0]
    finally:
        app.dependency_overrides.pop(get_db, None)

@pytest.mark.asyncio
async def test_direct_service_concurrent_idempotency(test_engine):
    org_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    async with test_engine.connect() as conn:
        session = AsyncSession(bind=conn)
        await seed_reference_data(session)
        user = User(id=admin_id, email=f'admin2_{admin_id}@example.com', username=f'admin2_{admin_id}', password_hash='x', is_active=True)
        org = Organization(id=org_id, name='Org', slug=f'org2-{org_id}')
        stmt = select(Role).where(Role.name == SystemRoleName.ADMIN)
        admin_role = (await session.execute(stmt)).scalar_one()
        member = OrganizationMember(organization_id=org_id, user_id=admin_id, role_id=admin_role.id)
        proj = Project(id=proj_id, organization_id=org_id, name='Proj', slug=f'proj2-{proj_id}', status=ProjectStatus.ACTIVE)
        art_id = uuid.uuid4()
        part = ProjectArtifact(id=art_id, project_id=proj_id, original_filename='x', content_hash='z', size_bytes=1, storage_key='w', upload_status=ArtifactUploadStatus.READY)
        scan = Scan(id=scan_id, project_id=proj_id, artifact_id=art_id, scan_type=ScanType.SECURITY, status=ScanStatus.COMPLETED)

        session.add_all([user, org, member, proj, part, scan])
        await session.commit()
        await session.close()

    report_in = ReportCreate(
        scan_id=scan_id,
        report_type='COMPLIANCE_REPORT',
        format='PDF'
    )

    async def execute_create():
        async with test_engine.connect() as conn:
            session = AsyncSession(bind=conn, expire_on_commit=False)
            try:
                report = await report_service.create_report(session, proj_id, org_id, admin_id, report_in)
                return report.id
            finally:
                await session.close()

    tasks = [execute_create() for _ in range(10)]
    results = await asyncio.gather(*tasks)

    report_ids = set(results)
    assert len(report_ids) == 1
