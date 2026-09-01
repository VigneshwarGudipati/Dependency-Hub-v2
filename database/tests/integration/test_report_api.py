import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import asyncio

from app.models.report import Report, ReportStatus, ReportType, ReportFormat
from app.models.organization import Organization
from app.models.project import Project, ProjectStatus
from app.models.scan import Scan, ScanStatus, ScanType
from app.models.user import User
from app.main import app
import pytest_asyncio

@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    from httpx import ASGITransport
    from app.core.dependencies import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
async def report_fixtures(seeded_session: AsyncSession):
    org_id = uuid.uuid4()
    org_id_2 = uuid.uuid4()
    proj_id = uuid.uuid4()
    proj_id_2 = uuid.uuid4()
    scan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user_id_2 = uuid.uuid4()

    org = Organization(id=org_id, name="Test Org", slug="test-org", is_active=True)
    org2 = Organization(id=org_id_2, name="Test Org 2", slug="test-org-2", is_active=True)
    proj = Project(id=proj_id, organization_id=org_id, name="Test Proj", slug="test-proj", status=ProjectStatus.ACTIVE)
    proj2 = Project(id=proj_id_2, organization_id=org_id_2, name="Test Proj 2", slug="test-proj-2", status=ProjectStatus.ACTIVE)

    from app.models.artifact import ProjectArtifact, ArtifactUploadStatus
    art_id = uuid.uuid4()
    art = ProjectArtifact(id=art_id, project_id=proj_id, uploaded_by=user_id, original_filename="test.zip", size_bytes=100, upload_status=ArtifactUploadStatus.READY, storage_key="test", content_hash="hash")
    scan = Scan(id=scan_id, project_id=proj_id, artifact_id=art_id, scan_type=ScanType.FULL, status=ScanStatus.COMPLETED)

    admin = User(id=user_id, email=f"admin_{user_id}@test.com", username=f"admin_{user_id}", password_hash="dummy", full_name="admin", is_active=True)
    viewer = User(id=user_id_2, email=f"viewer_{user_id_2}@test.com", username=f"viewer_{user_id_2}", password_hash="dummy", full_name="viewer", is_active=True)

    seeded_session.add_all([org, org2, proj, proj2, art, scan, admin, viewer])
    await seeded_session.flush()

    from sqlalchemy import select
    from app.models.role import Role, SystemRoleName
    from app.models.organization import OrganizationMember

    res_admin = await seeded_session.execute(select(Role).where(Role.name == SystemRoleName.ADMIN.value))
    admin_role = res_admin.scalar_one()

    res_viewer = await seeded_session.execute(select(Role).where(Role.name == SystemRoleName.VIEWER.value))
    viewer_role = res_viewer.scalar_one()

    member1 = OrganizationMember(organization_id=org_id, user_id=user_id, role_id=admin_role.id)
    member2 = OrganizationMember(organization_id=org_id, user_id=user_id_2, role_id=viewer_role.id)

    seeded_session.add_all([member1, member2])
    await seeded_session.commit()

    return {
        "org_id": org_id,
        "org_id_2": org_id_2,
        "proj_id": proj_id,
        "proj_id_2": proj_id_2,
        "scan_id": scan_id,
        "admin_id": user_id,
        "viewer_id": user_id_2
    }


def get_token(user_id: uuid.UUID) -> str:
    from app.core.security import create_access_token
    return create_access_token(str(user_id))


async def test_create_report_idempotency(client: AsyncClient, db_session: AsyncSession, report_fixtures):
    proj_id = report_fixtures["proj_id"]
    scan_id = report_fixtures["scan_id"]
    token = get_token(report_fixtures["admin_id"])
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "scan_id": str(scan_id),
        "report_type": "SECURITY_REPORT",
        "format": "JSON"
    }

    # 1. First create -> QUEUED
    resp1 = await client.post(f"/api/v1/projects/{proj_id}/reports", json=payload, headers=headers)
    if resp1.status_code != 201:
        print(resp1.json())
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["status"] == "QUEUED"
    report_id = data1["id"]

    # 2. Duplicate create -> Returns same QUEUED
    resp2 = await client.post(f"/api/v1/projects/{proj_id}/reports", json=payload, headers=headers)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == report_id

    # 3. Mark FAILED in DB and try again -> Returns FAILED
    await db_session.execute(update(Report).where(Report.id == uuid.UUID(report_id)).values(status=ReportStatus.FAILED))
    await db_session.commit()

    resp3 = await client.post(f"/api/v1/projects/{proj_id}/reports", json=payload, headers=headers)
    assert resp3.status_code == 201
    assert resp3.json()["id"] == report_id
    assert resp3.json()["status"] == "FAILED"

    # 4. Mark COMPLETED -> Returns COMPLETED
    await db_session.execute(update(Report).where(Report.id == uuid.UUID(report_id)).values(status=ReportStatus.COMPLETED))
    await db_session.commit()

    resp4 = await client.post(f"/api/v1/projects/{proj_id}/reports", json=payload, headers=headers)
    assert resp4.status_code == 201
    assert resp4.json()["id"] == report_id
    assert resp4.json()["status"] == "COMPLETED"





async def test_retry_endpoint(client: AsyncClient, db_session: AsyncSession, report_fixtures):
    proj_id = report_fixtures["proj_id"]
    scan_id = report_fixtures["scan_id"]
    token = get_token(report_fixtures["admin_id"])
    headers = {"Authorization": f"Bearer {token}"}

    # Create report and mark it FAILED
    report = Report(
        id=uuid.uuid4(),
        organization_id=report_fixtures["org_id"],
        project_id=proj_id,
        scan_id=scan_id,
        report_type=ReportType.EXECUTIVE_REPORT,
        format=ReportFormat.HTML,
        status=ReportStatus.FAILED,
        attempt_count=3
    )
    db_session.add(report)
    await db_session.commit()

    resp = await client.post(f"/api/v1/projects/{proj_id}/reports/{report.id}/retry", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "QUEUED"

    # Ensure attempt count is NOT reset by API
    await db_session.refresh(report)
    assert report.attempt_count == 3


async def test_cross_tenant_idor(client: AsyncClient, db_session: AsyncSession, report_fixtures):
    proj_id = report_fixtures["proj_id"]
    proj_id_2 = report_fixtures["proj_id_2"] # different org
    token = get_token(report_fixtures["admin_id"]) # belongs to org 1
    headers = {"Authorization": f"Bearer {token}"}

    report_id = uuid.uuid4()

    # Try to list reports in another org's project
    resp = await client.get(f"/api/v1/projects/{proj_id_2}/reports", headers=headers)
    assert resp.status_code == 404 # Project not found for this org

    # Try to create
    payload = {"scan_id": str(report_fixtures["scan_id"]), "report_type": "SECURITY_REPORT", "format": "JSON"}
    resp = await client.post(f"/api/v1/projects/{proj_id_2}/reports", json=payload, headers=headers)
    assert resp.status_code == 404

    # Try to get detail
    resp = await client.get(f"/api/v1/projects/{proj_id_2}/reports/{report_id}", headers=headers)
    assert resp.status_code == 404

    # Try to download
    resp = await client.get(f"/api/v1/projects/{proj_id_2}/reports/{report_id}/download", headers=headers)
    assert resp.status_code == 404

    # Try to retry
    resp = await client.post(f"/api/v1/projects/{proj_id_2}/reports/{report_id}/retry", headers=headers)
    assert resp.status_code == 404

    # Try to delete
    resp = await client.delete(f"/api/v1/projects/{proj_id_2}/reports/{report_id}", headers=headers)
    assert resp.status_code == 404


async def test_viewer_rbac(client: AsyncClient, db_session: AsyncSession, report_fixtures):
    proj_id = report_fixtures["proj_id"]
    token = get_token(report_fixtures["viewer_id"])
    headers = {"Authorization": f"Bearer {token}"}

    report_id = uuid.uuid4()

    # 1. Viewer cannot create
    payload = {"scan_id": str(report_fixtures["scan_id"]), "report_type": "SECURITY_REPORT", "format": "JSON"}
    resp1 = await client.post(f"/api/v1/projects/{proj_id}/reports", json=payload, headers=headers)
    assert resp1.status_code == 403

    # 2. Viewer cannot retry
    resp = await client.post(f"/api/v1/projects/{proj_id}/reports/{report_id}/retry", headers=headers)
    assert resp.status_code == 403

    # 3. Viewer cannot delete
    resp = await client.delete(f"/api/v1/projects/{proj_id}/reports/{report_id}", headers=headers)
    assert resp.status_code == 403

    # 4. Viewer can list
    resp2 = await client.get(f"/api/v1/projects/{proj_id}/reports", headers=headers)
    assert resp2.status_code == 200
    assert isinstance(resp2.json(), list)
