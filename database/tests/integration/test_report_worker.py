import uuid
import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select
from datetime import timedelta

from app.models.report import Report, ReportStatus, ReportType, ReportFormat
from app.models.organization import Organization
from app.models.project import Project, ProjectStatus
from app.models.scan import Scan, ScanStatus, ScanType
from app.workers.report_worker import ReportWorker, MAX_ATTEMPTS, MAX_ORG_CONCURRENCY
from app.models.base import utc_now


@pytest.fixture
async def worker_fixtures(db_session: AsyncSession):
    await db_session.execute(update(Report).values(status=ReportStatus.FAILED))
    await db_session.commit()
    org_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    scan_id = uuid.uuid4()

    org = Organization(id=org_id, name="Worker Org", slug="worker-org", is_active=True)
    proj = Project(id=proj_id, organization_id=org_id, name="Worker Proj", slug="worker-proj", status=ProjectStatus.ACTIVE)
    from app.models.artifact import ProjectArtifact, ArtifactUploadStatus
    art_id = uuid.uuid4()
    art = ProjectArtifact(id=art_id, project_id=proj_id, uploaded_by=None, original_filename="test.zip", size_bytes=100, upload_status=ArtifactUploadStatus.READY, storage_key="test", content_hash="hash")
    scan = Scan(id=scan_id, project_id=proj_id, artifact_id=art_id, scan_type=ScanType.FULL, status=ScanStatus.COMPLETED)

    db_session.add_all([org, proj, art, scan])
    await db_session.commit()
    return {
        "org_id": org_id,
        "proj_id": proj_id,
        "scan_id": scan_id,
        "art_id": art_id
    }


async def test_worker_claim_atomic(db_session: AsyncSession, worker_fixtures):
    # 1. Create a queued report
    report = Report(
        id=uuid.uuid4(),
        organization_id=worker_fixtures["org_id"],
        project_id=worker_fixtures["proj_id"],
        scan_id=worker_fixtures["scan_id"],
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.JSON,
        status=ReportStatus.QUEUED,
        attempt_count=0
    )
    db_session.add(report)
    await db_session.commit()

    worker = ReportWorker()

    # 2. Claim it
    claimed_report, token = await worker.claim_job(db_session)
    assert claimed_report is not None
    assert token is not None
    assert claimed_report.id == report.id
    assert claimed_report.status == ReportStatus.GENERATING
    assert claimed_report.attempt_count == 1
    assert claimed_report.worker_id == worker.worker_id
    assert claimed_report.generation_token == token
    assert claimed_report.lease_expires_at > utc_now()


async def test_worker_concurrency_cap(db_session: AsyncSession, worker_fixtures):
    org_id = worker_fixtures["org_id"]
    proj_id = worker_fixtures["proj_id"]
    scan_id = worker_fixtures["scan_id"]

    art_id = worker_fixtures["art_id"]

    # 1. Create MAX_ORG_CONCURRENCY + 2 reports
    reports = []
    scans = []
    for i in range(MAX_ORG_CONCURRENCY + 2):
        s_id = uuid.uuid4()
        scans.append(Scan(id=s_id, project_id=proj_id, artifact_id=art_id, scan_type=ScanType.FULL, status=ScanStatus.COMPLETED))
        r = Report(
            id=uuid.uuid4(),
            organization_id=org_id,
            project_id=proj_id,
            scan_id=s_id,
            report_type=ReportType.PACKAGE_REPORT,
            format=ReportFormat.JSON,
            status=ReportStatus.QUEUED,
            attempt_count=0
        )
        reports.append(r)

    db_session.add_all(scans)
    db_session.add_all(reports)
    await db_session.commit()

    worker = ReportWorker()
    claimed = 0

    # Try to claim all
    for _ in range(len(reports)):
        c, t = await worker.claim_job(db_session)
        if c:
            claimed += 1

    assert claimed == MAX_ORG_CONCURRENCY

    # The remaining 2 should not be claimable by ANY worker
    c2, t2 = await worker.claim_job(db_session)
    assert c2 is None


async def test_worker_stale_recovery(db_session: AsyncSession, worker_fixtures):
    now = utc_now()
    report = Report(
        id=uuid.uuid4(),
        organization_id=worker_fixtures["org_id"],
        project_id=worker_fixtures["proj_id"],
        scan_id=worker_fixtures["scan_id"],
        report_type=ReportType.EXECUTIVE_REPORT,
        format=ReportFormat.PDF,
        status=ReportStatus.GENERATING,
        attempt_count=1,
        worker_id="old-dead-worker",
        generation_token="old-token",
        generation_started_at=now - timedelta(minutes=20),
        lease_expires_at=now - timedelta(minutes=10) # STALE
    )
    db_session.add(report)
    await db_session.commit()

    worker = ReportWorker()
    claimed, token = await worker.claim_job(db_session)

    assert claimed is not None
    assert claimed.id == report.id
    assert claimed.worker_id == worker.worker_id
    assert claimed.attempt_count == 2
    assert claimed.generation_token != "old-token"


async def test_worker_permanent_failure(db_session: AsyncSession, worker_fixtures):
    now = utc_now()
    report = Report(
        id=uuid.uuid4(),
        organization_id=worker_fixtures["org_id"],
        project_id=worker_fixtures["proj_id"],
        scan_id=worker_fixtures["scan_id"],
        report_type=ReportType.COMPLIANCE_REPORT,
        format=ReportFormat.JSON,
        status=ReportStatus.GENERATING,
        attempt_count=MAX_ATTEMPTS, # Max reached
        worker_id="dead-worker",
        generation_token="token",
        lease_expires_at=now - timedelta(minutes=10)
    )
    db_session.add(report)
    await db_session.commit()

    worker = ReportWorker()

    # 1. Stale recovery should mark it FAILED
    await worker.recover_permanent_failures(db_session)

    await db_session.refresh(report)
    assert report.status == ReportStatus.FAILED
    assert report.error_category == "JOB_TIMEOUT"

    # 2. It should not be claimable
    claimed, _ = await worker.claim_job(db_session)
    assert claimed is None

async def test_worker_split_brain_write(db_session: AsyncSession, worker_fixtures):
    # Simulate Worker A with lease
    now = utc_now()
    report_id = uuid.uuid4()
    report = Report(
        id=report_id,
        organization_id=worker_fixtures['org_id'],
        project_id=worker_fixtures['proj_id'],
        scan_id=worker_fixtures['scan_id'],
        report_type=ReportType.COMPLIANCE_REPORT,
        format=ReportFormat.JSON,
        status=ReportStatus.GENERATING,
        attempt_count=1,
        worker_id='Worker-A',
        generation_token='TOKEN-A',
        lease_expires_at=now - timedelta(minutes=1) # Expired
    )
    db_session.add(report)
    await db_session.commit()

    # Worker B claims
    worker_b = ReportWorker()
    claimed, token_b = await worker_b.claim_job(db_session)
    assert claimed.id == report.id
    assert claimed.worker_id == worker_b.worker_id
    assert token_b != 'TOKEN-A'

    # Worker A resumes and tries to generate/complete
    from app.services.reporting.report_generation_service import ReportGenerationService
    success = await ReportGenerationService.generate_report(db_session, report.id, 'Worker-A', 'TOKEN-A')
    assert success is False

    # Verify Worker B is still authoritative
    await db_session.refresh(report)
    assert report.worker_id == worker_b.worker_id
    assert report.generation_token == token_b
    assert report.status == ReportStatus.GENERATING

async def test_artifact_reconciliation(db_session: AsyncSession, worker_fixtures):
    now = utc_now()
    report_id = uuid.uuid4()
    report = Report(
        id=report_id,
        organization_id=worker_fixtures['org_id'],
        project_id=worker_fixtures['proj_id'],
        scan_id=worker_fixtures['scan_id'],
        report_type=ReportType.COMPLIANCE_REPORT,
        format=ReportFormat.JSON,
        status=ReportStatus.GENERATING,
        attempt_count=1,
        worker_id='Worker-A',
        generation_token='TOKEN-A',
        lease_expires_at=now - timedelta(minutes=1) # Expired
    )
    db_session.add(report)

    # Simulate Worker A inserted artifact but didn't complete report
    from app.models.report import ReportArtifact, ReportEncryptionMetadata
    artifact_id = uuid.uuid4()
    artifact = ReportArtifact(
        id=artifact_id,
        report_id=report_id,
        format=ReportFormat.JSON,
        encrypted_data=b'stale-data',
        generation_token='TOKEN-A',
        artifact_size_bytes=10,
        content_type='application/json',
        artifact_sha256='checksumA'
    )
    enc_meta = ReportEncryptionMetadata(
        id=uuid.uuid4(),
        artifact_id=artifact_id,
        algorithm='AES',
        encryption_version='v1',
        key_reference='key',
        initialization_vector='iv',
        authentication_tag='tag',
        encrypted_dek_reference='dek',
        checksum='checksumA'
    )
    db_session.add(artifact)
    db_session.add(enc_meta)
    await db_session.commit()

    # Worker B claims and generates
    worker_b = ReportWorker()
    claimed, token_b = await worker_b.claim_job(db_session)
    assert claimed is not None

    from app.services.reporting.report_generation_service import ReportGenerationService
    success = await ReportGenerationService.generate_report(db_session, report.id, worker_b.worker_id, token_b)
    assert success is True

    # Verify Artifact is now from Worker B and only 1 exists
    stmt = select(ReportArtifact).where(ReportArtifact.report_id == report_id)
    artifacts = (await db_session.execute(stmt)).scalars().all()
    assert len(artifacts) == 1
    assert artifacts[0].generation_token == token_b
    assert artifacts[0].id != artifact_id # It was replaced
