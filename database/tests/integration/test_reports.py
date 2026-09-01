"""Model tests for P2 Reporting architecture."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.project import Project, ProjectType, ProjectVisibility
from app.models.scan import Scan, ScanType, ScanStatus
from app.models.user import User
from app.models.artifact import ProjectArtifact, ArtifactSourceType
from app.models.report import (
    Report, ReportSnapshot, ReportArtifact, ReportEncryptionMetadata,
    ReportType, ReportStatus, ReportFormat
)

@pytest.mark.asyncio
async def test_report_model_construction_and_tenant_ownership(db_session: AsyncSession, sample_org: Organization, sample_user: User):
    """Test basic construction and that tenant fields exist."""
    project = Project(
        name="Report Test",
        slug="report-test",
        organization_id=sample_org.id,
        project_type=ProjectType.WEB,
        visibility=ProjectVisibility.PRIVATE,
        created_by=sample_user.id
    )
    db_session.add(project)
    await db_session.flush()

    report = Report(
        organization_id=sample_org.id,
        project_id=project.id,
        created_by=sample_user.id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.JSON,
        status=ReportStatus.QUEUED,
    )
    db_session.add(report)
    await db_session.flush()

    assert report.id is not None
    assert report.organization_id == sample_org.id
    assert report.project_id == project.id
    assert report.scan_id is None  # Nullable scan_id
    assert report.format == ReportFormat.JSON

@pytest.mark.asyncio
async def test_snapshot_and_artifact_attachment(db_session: AsyncSession, sample_org: Organization):
    """Test 1-to-1 snapshot and 1-to-many artifacts with encryption metadata."""
    project = Project(
        name="Report Attach Test",
        slug="report-attach",
        organization_id=sample_org.id,
    )
    db_session.add(project)
    await db_session.flush()

    report = Report(
        organization_id=sample_org.id,
        project_id=project.id,
        report_type=ReportType.PACKAGE_REPORT,
        format=ReportFormat.PDF,
    )
    db_session.add(report)
    await db_session.flush()

    snapshot = ReportSnapshot(
        report_id=report.id,
        snapshot_data={"dependencies": []},
        schema_version="1.0",
        snapshot_sha256="fakehash",
    )
    db_session.add(snapshot)

    pdf_artifact = ReportArtifact(
        report_id=report.id,
        format=ReportFormat.PDF,
        encrypted_data=b"encryptedpdf",
        artifact_size_bytes=100,
        content_type="application/pdf",
        artifact_sha256="pdfhash",
    )
    db_session.add(pdf_artifact)
    await db_session.flush()

    encryption = ReportEncryptionMetadata(
        artifact_id=pdf_artifact.id,
        key_reference="test-key",
        initialization_vector="iv",
        authentication_tag="tag",
        encrypted_dek_reference="dek",
        checksum="chk",
    )
    db_session.add(encryption)
    await db_session.flush()

    # Verify attachments
    stmt = select(Report).where(Report.id == report.id).options(
        selectinload(Report.snapshot),
        selectinload(Report.artifacts).selectinload(ReportArtifact.encryption_metadata)
    )
    result = await db_session.execute(stmt)
    saved_report = result.unique().scalar_one()

    assert saved_report.snapshot.snapshot_sha256 == "fakehash"
    assert len(saved_report.artifacts) == 1
    assert saved_report.artifacts[0].format == ReportFormat.PDF
    assert saved_report.artifacts[0].encryption_metadata.key_reference == "test-key"

@pytest.mark.asyncio
async def test_report_survives_scan_deletion(db_session: AsyncSession, sample_org: Organization):
    """Prove scan deletion does NOT cascade to report."""
    project = Project(name="Del Test", slug="del-test", organization_id=sample_org.id)
    db_session.add(project)
    await db_session.flush()

    artifact = ProjectArtifact(
        project_id=project.id,
        original_filename="test.json",
        storage_key="test/test.json",
        content_hash="hash"
    )
    db_session.add(artifact)
    await db_session.flush()

    scan = Scan(project_id=project.id, artifact_id=artifact.id)
    db_session.add(scan)
    await db_session.flush()

    report = Report(
        organization_id=sample_org.id,
        project_id=project.id,
        scan_id=scan.id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.JSON,
    )
    db_session.add(report)
    await db_session.flush()

    # Delete scan
    await db_session.delete(scan)
    await db_session.flush()

    # Verify report survives and scan_id is NULL
    await db_session.refresh(report)
    assert report.scan_id is None
    assert report.id is not None

@pytest.mark.asyncio
async def test_report_survives_user_deletion(db_session: AsyncSession, sample_org: Organization, sample_user: User):
    """Prove user deletion sets created_by to NULL but report survives."""
    project = Project(name="User Test", slug="usr-test", organization_id=sample_org.id)
    db_session.add(project)
    await db_session.flush()

    report = Report(
        organization_id=sample_org.id,
        project_id=project.id,
        created_by=sample_user.id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.JSON,
    )
    db_session.add(report)
    await db_session.flush()

    # Delete user
    await db_session.delete(sample_user)
    await db_session.flush()

    # Verify report survives
    await db_session.refresh(report)
    assert report.created_by is None

@pytest.mark.asyncio
async def test_project_deletion_cascades(db_session: AsyncSession, sample_org: Organization):
    """Prove project deletion cascades to report (no conflicting delete-orphan)."""
    project = Project(name="Proj Test", slug="proj-test", organization_id=sample_org.id)
    db_session.add(project)
    await db_session.flush()

    report = Report(
        organization_id=sample_org.id,
        project_id=project.id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.JSON,
    )
    db_session.add(report)
    await db_session.flush()
    report_id = report.id

    await db_session.delete(project)
    await db_session.flush()

    # Report should be deleted
    stmt = select(Report).where(Report.id == report_id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_artifact_uniqueness_constraint(db_session: AsyncSession, sample_org: Organization):
    """Prove (report_id, format) is unique for ReportArtifact."""
    project = Project(name="Uniq Test", slug="uniq-test", organization_id=sample_org.id)
    db_session.add(project)
    await db_session.flush()

    report = Report(
        organization_id=sample_org.id,
        project_id=project.id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.PDF,
    )
    db_session.add(report)
    await db_session.flush()

    artifact1 = ReportArtifact(
        report_id=report.id,
        format=ReportFormat.PDF,
        encrypted_data=b"data",
        content_type="app/pdf",
        artifact_sha256="hash1",
    )
    db_session.add(artifact1)
    await db_session.flush()

    artifact2 = ReportArtifact(
        report_id=report.id,
        format=ReportFormat.PDF,  # Duplicate format
        encrypted_data=b"data",
        content_type="app/pdf",
        artifact_sha256="hash2",
    )
    async with db_session.begin_nested():
        db_session.add(artifact2)
        with pytest.raises(IntegrityError):
            await db_session.flush()

@pytest.mark.asyncio
async def test_report_idempotency_constraint(db_session: AsyncSession, sample_org: Organization):
    """Prove composite uniqueness on (project_id, scan_id, report_type, format) and durability."""
    project = Project(name="Idemp Test", slug="idemp-test", organization_id=sample_org.id)
    db_session.add(project)
    await db_session.flush()

    artifact = ProjectArtifact(
        project_id=project.id,
        original_filename="test.json",
        storage_key="test/test.json",
        content_hash="hash"
    )
    db_session.add(artifact)
    await db_session.flush()

    scan = Scan(project_id=project.id, artifact_id=artifact.id)
    db_session.add(scan)
    await db_session.flush()

    # 1. Test Durability (Format persistence)
    org_id = sample_org.id
    proj_id = project.id
    scn_id = scan.id
    report1 = Report(
        organization_id=org_id,
        project_id=proj_id,
        scan_id=scn_id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.PDF,
        status=ReportStatus.QUEUED
    )
    db_session.add(report1)
    await db_session.flush()

    # Reload from DB
    report_id = report1.id
    db_session.expunge(report1)

    reloaded = (await db_session.execute(select(Report).where(Report.id == report_id))).scalar_one()
    assert reloaded.format == ReportFormat.PDF

    # 2. Test Idempotency constraint - identical dimensions should fail
    report2_duplicate = Report(
        organization_id=org_id,
        project_id=proj_id,
        scan_id=scn_id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.PDF,
        status=ReportStatus.QUEUED
    )
    async with db_session.begin_nested():
        db_session.add(report2_duplicate)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # 3. Different format should succeed
    report3_diff_format = Report(
        organization_id=org_id,
        project_id=proj_id,
        scan_id=scn_id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.JSON,
        status=ReportStatus.QUEUED
    )
    db_session.add(report3_diff_format)
    await db_session.flush()

    # 4. Different report_type should succeed
    report4_diff_type = Report(
        organization_id=org_id,
        project_id=proj_id,
        scan_id=scn_id,
        report_type=ReportType.PACKAGE_REPORT,
        format=ReportFormat.PDF,
        status=ReportStatus.QUEUED
    )
    db_session.add(report4_diff_type)
    await db_session.flush()

    # 5. Different scan should succeed
    scan2 = Scan(project_id=proj_id, artifact_id=artifact.id)
    db_session.add(scan2)
    await db_session.flush()

    report5_diff_scan = Report(
        organization_id=org_id,
        project_id=proj_id,
        scan_id=scan2.id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.PDF,
        status=ReportStatus.QUEUED
    )
    db_session.add(report5_diff_scan)
    await db_session.flush()

import uuid
import asyncio
from datetime import datetime, timedelta
from app.models.base import utc_now

@pytest.mark.asyncio
async def test_report_worker_durability_fields(db_session: AsyncSession, sample_org: Organization):
    """Prove persistence of new P2.3 schema fields."""
    project = Project(name="Worker Test", slug="worker-test", organization_id=sample_org.id)
    db_session.add(project)
    await db_session.flush()

    report = Report(
        organization_id=sample_org.id,
        project_id=project.id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.JSON,
        status=ReportStatus.QUEUED,
        generation_started_at=utc_now(),
        error_category="JOB_TIMEOUT",
        attempt_count=1,
        worker_id="worker-123",
        lease_expires_at=utc_now() + timedelta(minutes=5),
        generation_token=str(uuid.uuid4())
    )
    db_session.add(report)
    await db_session.flush()

    # Expunge and reload
    r_id = report.id
    db_session.expunge(report)

    reloaded = (await db_session.execute(select(Report).where(Report.id == r_id))).scalar_one()
    assert reloaded.generation_started_at is not None
    assert reloaded.error_category == "JOB_TIMEOUT"
    assert reloaded.attempt_count == 1
    assert reloaded.worker_id == "worker-123"
    assert reloaded.lease_expires_at is not None
    assert reloaded.generation_token is not None

@pytest.mark.asyncio
async def test_report_sequential_state_transition_verification(db_session: AsyncSession, sample_org: Organization):
    """Test sequential state-transition of worker claim."""
    project = Project(name="Claim Test", slug="claim-test", organization_id=sample_org.id)
    db_session.add(project)
    await db_session.flush()

    report = Report(
        organization_id=sample_org.id,
        project_id=project.id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.JSON,
        status=ReportStatus.QUEUED,
    )
    db_session.add(report)
    await db_session.flush()
    r_id = report.id
    await db_session.commit()

    async def worker_claim(worker_name):
        # In a test environment, session binds to the same transaction.
        # To simulate SKIP LOCKED, if the status is no longer QUEUED, we return None.
        async with db_session.begin_nested():
            stmt = select(Report).where(
                Report.id == r_id,
                Report.status == ReportStatus.QUEUED
            ).with_for_update(skip_locked=True)

            result = await db_session.execute(stmt)
            claimed_report = result.scalar_one_or_none()
            if claimed_report:
                claimed_report.status = ReportStatus.GENERATING
                claimed_report.worker_id = worker_name
                claimed_report.attempt_count += 1
                return worker_name
            return None

    # Simulate sequential execution which mimics exactly what happens when one
    # worker acquires the SKIP LOCKED and the other misses it or sees GENERATING.
    winner = await worker_claim("worker_A")
    loser = await worker_claim("worker_B")

    assert winner == "worker_A"
    assert loser is None

    final_report = (await db_session.execute(select(Report).where(Report.id == r_id))).scalar_one()
    assert final_report.status == ReportStatus.GENERATING
    assert final_report.worker_id == "worker_A"
    assert final_report.attempt_count == 1


@pytest.mark.asyncio
async def test_report_split_brain_invariant(db_session: AsyncSession, sample_org: Organization):
    """Test unit/integration invariant for split-brain protection using generation_token conditional updates."""
    project = Project(name="SplitBrain", slug="sb-test", organization_id=sample_org.id)
    db_session.add(project)
    await db_session.flush()

    token_a = str(uuid.uuid4())
    report = Report(
        organization_id=sample_org.id,
        project_id=project.id,
        report_type=ReportType.SECURITY_REPORT,
        format=ReportFormat.JSON,
        status=ReportStatus.GENERATING,
        worker_id="worker_a",
        generation_token=token_a,
        lease_expires_at=utc_now() - timedelta(minutes=10) # Expired
    )
    db_session.add(report)
    await db_session.flush()

    # Worker B reclaims the job
    token_b = str(uuid.uuid4())
    report.worker_id = "worker_b"
    report.generation_token = token_b
    report.lease_expires_at = utc_now() + timedelta(minutes=5)
    await db_session.flush()

    # Worker A attempts to complete it by running a conditional update
    from sqlalchemy import update
    stmt = update(Report).where(
        Report.id == report.id,
        Report.status == ReportStatus.GENERATING,
        Report.generation_token == token_a
    ).values(status=ReportStatus.COMPLETED)

    result = await db_session.execute(stmt)
    assert result.rowcount == 0 # Worker A failed to update

    # Worker B attempts to complete it
    stmt2 = update(Report).where(
        Report.id == report.id,
        Report.status == ReportStatus.GENERATING,
        Report.generation_token == token_b
    ).values(status=ReportStatus.COMPLETED)

    result2 = await db_session.execute(stmt2)
    assert result2.rowcount == 1 # Worker B succeeded
