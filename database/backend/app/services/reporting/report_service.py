"""Report orchestration service."""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.report import Report, ReportStatus, ReportArtifact
from app.models.scan import Scan, ScanStatus
from app.models.project import Project
from app.models.audit import AuditLog, AuditAction
from app.schemas.report import ReportCreate
from app.models.base import utc_now


async def get_report_or_404(
    db: AsyncSession,
    report_id: uuid.UUID,
    organization_id: uuid.UUID,
    project_id: uuid.UUID
) -> Report:
    """Get report securely or raise 404."""
    stmt = select(Report).where(
        Report.id == report_id,
        Report.organization_id == organization_id,
        Report.project_id == project_id
    )
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


async def create_report(
    db: AsyncSession,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    report_in: ReportCreate
) -> Report:
    """Idempotently create a new report generation request."""

    # 1. Validate scan ownership
    stmt = select(Scan).where(
        Scan.id == report_in.scan_id,
        Scan.project_id == project_id
    )
    scan = (await db.execute(stmt)).scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=422, detail="Scan does not exist or does not belong to project")

    if scan.status != ScanStatus.COMPLETED:
        raise HTTPException(status_code=422, detail="Scan is not completed")

    # The organization concurrency cap (5 GENERATING per org) is handled by the worker claim loop.
    # The API will simply enqueue the job, and the worker will respect the cap when pulling.

    report_id = uuid.uuid4()
    report = Report(
        id=report_id,
        organization_id=organization_id,
        project_id=project_id,
        scan_id=report_in.scan_id,
        created_by=user_id,
        report_type=report_in.report_type,
        format=report_in.format,
        status=ReportStatus.QUEUED,
        attempt_count=0
    )
    db.add(report)

    # Log action
    audit_log = AuditLog(
        id=uuid.uuid4(),
        organization_id=organization_id,
        user_id=user_id,
        action=AuditAction.REPORT_CREATED,
        entity_type="Report",
        entity_id=str(report_id)
    )
    db.add(audit_log)

    try:
        await db.commit()
        await db.refresh(report)
        return report
    except IntegrityError:
        # Constraint uq_report_project_scan_type_format prevents duplicates
        await db.rollback()

        # Re-query the existing report
        stmt = select(Report).where(
            Report.project_id == project_id,
            Report.scan_id == report_in.scan_id,
            Report.report_type == report_in.report_type,
            Report.format == report_in.format
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if not existing:
            # Should not happen unless deleted immediately after conflict
            raise HTTPException(status_code=500, detail="Concurrency conflict retrieving report")

        return existing


async def retry_report(
    db: AsyncSession,
    report_id: uuid.UUID,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_id: uuid.UUID
) -> Report:
    """Explicit retry for FAILED reports."""
    report = await get_report_or_404(db, report_id, organization_id, project_id)

    if report.status != ReportStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only FAILED reports can be retried")

    report.status = ReportStatus.QUEUED
    report.error_category = None

    audit_log = AuditLog(
        id=uuid.uuid4(),
        organization_id=organization_id,
        user_id=user_id,
        action=AuditAction.REPORT_RETRY_REQUESTED,
        entity_type="Report",
        entity_id=str(report_id)
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(report)
    return report


async def list_reports(
    db: AsyncSession,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    report_type: Optional[str] = None,
    format: Optional[str] = None
) -> List[Report]:
    """List reports with pagination and filtering."""

    stmt = select(Report).where(
        Report.project_id == project_id,
        Report.organization_id == organization_id
    )

    if status:
        try:
            enum_status = ReportStatus(status.upper())
            stmt = stmt.where(Report.status == enum_status)
        except ValueError:
            pass

    if report_type:
        from app.models.report import ReportType
        try:
            enum_type = ReportType(report_type.upper())
            stmt = stmt.where(Report.report_type == enum_type)
        except ValueError:
            pass

    if format:
        from app.models.report import ReportFormat
        try:
            enum_format = ReportFormat(format.upper())
            stmt = stmt.where(Report.format == enum_format)
        except ValueError:
            pass

    stmt = stmt.order_by(Report.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def delete_report(
    db: AsyncSession,
    report_id: uuid.UUID,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_id: uuid.UUID
) -> None:
    """Delete a report and cascade delete its artifacts."""
    report = await get_report_or_404(db, report_id, organization_id, project_id)

    await db.delete(report)

    audit_log = AuditLog(
        id=uuid.uuid4(),
        organization_id=organization_id,
        user_id=user_id,
        action=AuditAction.REPORT_DELETED,
        entity_type="Report",
        entity_id=str(report_id)
    )
    db.add(audit_log)

    await db.commit()


from app.services.encryption_service import decrypt_artifact
from app.models.report import ReportEncryptionMetadata
from app.services.reporting.filename import generate_safe_filename

async def download_report(
    db: AsyncSession,
    report_id: uuid.UUID,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_id: uuid.UUID
) -> tuple[bytes, str, str]:
    """Download and decrypt a report artifact."""
    report = await get_report_or_404(db, report_id, organization_id, project_id)

    if report.status != ReportStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Report is not completed")

    stmt = select(ReportArtifact).where(ReportArtifact.report_id == report_id)
    artifact = (await db.execute(stmt)).scalar_one_or_none()

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    stmt_meta = select(ReportEncryptionMetadata).where(ReportEncryptionMetadata.artifact_id == artifact.id)
    meta = (await db.execute(stmt_meta)).scalar_one_or_none()

    if not meta:
        raise HTTPException(status_code=500, detail="Encryption metadata missing")

    from app.services.encryption_service import key_provider
    try:
        dek = key_provider.decrypt_dek(meta.encrypted_dek_reference)
        plaintext = decrypt_artifact(
            ciphertext=artifact.encrypted_data,
            dek=dek,
            b64_nonce=meta.initialization_vector,
            b64_tag=meta.authentication_tag
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Decryption failed")

    audit_log = AuditLog(
        id=uuid.uuid4(),
        organization_id=organization_id,
        user_id=user_id,
        action=AuditAction.REPORT_DOWNLOADED,
        entity_type="Report",
        entity_id=str(report_id)
    )
    db.add(audit_log)
    await db.commit()

    filename = generate_safe_filename(f"report_{report_id}", artifact.format.lower(), artifact.format.lower())
    return plaintext, filename, artifact.content_type
