"""Report Generation Orchestration Service."""

import hashlib
import logging
import uuid
import base64
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.report import Report, ReportStatus, ReportArtifact, ReportEncryptionMetadata
from app.models.audit import AuditLog, AuditAction
from app.services.snapshot_service import SnapshotService, SnapshotGenerationError
from app.services.reporting.report_data import ReportData
from app.services.reporting.report_document import ReportDocument
from app.services.reporting.exporter import ExporterRegistry
from app.services.encryption_service import key_provider, encrypt_artifact
from app.models.base import utc_now

logger = logging.getLogger(__name__)


class ReportGenerationError(Exception):
    """Base error for generation."""
    def __init__(self, message: str, error_category: str):
        super().__init__(message)
        self.error_category = error_category


class ReportGenerationService:
    """Orchestrates the conversion of a Report request into an encrypted Artifact."""

    @classmethod
    async def generate_report(
        cls,
        db: AsyncSession,
        report_id: uuid.UUID,
        worker_id: str,
        generation_token: str
    ) -> bool:
        """
        Executes the full pipeline for a claimed report.
        Returns True if successful, False if the worker lost the lease or failed permanently.
        """
        # 1. Load and validate Report
        stmt = select(Report).where(Report.id == report_id)
        report = (await db.execute(stmt)).scalar_one_or_none()

        if not report:
            logger.error(f"Report {report_id} not found during generation")
            return False

        if report.status != ReportStatus.GENERATING:
            logger.error(f"Report {report_id} is not GENERATING")
            return False

        if report.worker_id != worker_id or report.generation_token != generation_token:
            logger.error(f"Worker {worker_id} lost lease for report {report_id}")
            return False

        try:
            # 2. Obtain/reuse ReportSnapshot
            # SnapshotService automatically handles reuse and concurrent race conditions via savepoints.
            snapshot = await SnapshotService.create_snapshot(db, report.id)

            # 3 & 4. Construct ReportData and ReportDocument
            report_data = ReportData.from_snapshot(snapshot.snapshot_data)
            report_document = ReportDocument.from_report_data(report_data)

            # 5. Select Exporter
            exporter = ExporterRegistry.get_exporter(report.format.lower())

            # 6. Generate plaintext bytes
            plaintext_bytes = exporter.export(report_document)

            # 7 & 8. Encrypt using existing envelope encryption
            dek, b64_encrypted_dek = key_provider.generate_dek()
            ciphertext, b64_nonce, b64_tag, b64_checksum = encrypt_artifact(plaintext_bytes, dek)
            artifact_size = len(plaintext_bytes)

            content_type_map = {
                "json": "application/json",
                "html": "text/html",
                "pdf": "application/pdf",
                "csv": "text/csv",
                "sarif": "application/sarif+json"
            }
            content_type = content_type_map.get(report.format.lower(), "application/octet-stream")

            # 9 & 10. Persist ReportArtifact and EncryptionMetadata safely (Reconciliation)
            artifact_id = uuid.uuid4()
            artifact = ReportArtifact(
                id=artifact_id,
                report_id=report.id,
                format=report.format,
                encrypted_data=ciphertext,
                generation_token=generation_token,
                artifact_size_bytes=artifact_size,
                content_type=content_type,
                artifact_sha256=b64_checksum
            )

            enc_meta = ReportEncryptionMetadata(
                id=uuid.uuid4(),
                artifact_id=artifact_id,
                algorithm="AES-256-GCM",
                encryption_version="v1",
                key_reference="local_master_key",
                initialization_vector=b64_nonce,
                authentication_tag=b64_tag,
                encrypted_dek_reference=b64_encrypted_dek,
                checksum=b64_checksum
            )

            try:
                async with db.begin_nested():
                    db.add(artifact)
                    db.add(enc_meta)
                    await db.flush()
            except IntegrityError:
                # 10b. Artifact Reconciliation
                # Another worker lost its lease AFTER inserting the artifact but BEFORE completing the report.
                logger.info(f"Artifact reconciliation triggered for report {report_id} and format {report.format}")
                existing_stmt = select(ReportArtifact).where(
                    ReportArtifact.report_id == report.id,
                    ReportArtifact.format == report.format
                )
                existing_artifact = (await db.execute(existing_stmt)).scalar_one_or_none()
                if not existing_artifact:
                    raise ReportGenerationError("Failed to reconcile artifact during IntegrityError", "DATABASE_ERROR")

                if existing_artifact.generation_token == generation_token:
                    # Very rare: somehow our own artifact was already inserted. Safe to proceed.
                    pass
                else:
                    # Stale artifact from a previous failed generation attempt (lease lost).
                    # Delete it and insert the current authoritative artifact.
                    await db.delete(existing_artifact)
                    await db.flush() # Flush deletion
                    async with db.begin_nested():
                        db.add(artifact)
                        db.add(enc_meta)
                        await db.flush()

            # 11. Atomically finalize Report state
            # Ensure the worker still owns the lease before finalizing
            update_stmt = (
                update(Report)
                .where(
                    Report.id == report.id,
                    Report.status == ReportStatus.GENERATING,
                    Report.worker_id == worker_id,
                    Report.generation_token == generation_token
                )
                .values(
                    status=ReportStatus.COMPLETED,
                    completed_at=utc_now(),
                    error_category=None
                )
            )
            result = await db.execute(update_stmt)
            if result.rowcount == 0:
                # We lost the lease during generation.
                # The artifact was persisted, but we don't own the completion.
                # We rollback the entire transaction (including artifact creation, unless it was already created by another).
                logger.warning(f"Worker {worker_id} lost lease during completion of report {report_id}")
                await db.rollback()
                return False

            # 12. Write safe audit events
            audit_log = AuditLog(
                id=uuid.uuid4(),
                organization_id=report.organization_id,
                user_id=None,  # System action
                action=AuditAction.REPORT_GENERATION_COMPLETED,
                entity_type="Report",
                entity_id=str(report.id)
            )
            db.add(audit_log)
            await db.commit()
            return True

        except SnapshotGenerationError as e:
            logger.error(f"Snapshot failure for report {report_id}: {str(e)}")
            await cls._handle_failure(db, report_id, worker_id, generation_token, "SNAPSHOT_FAILED")
            return False
        except Exception as e:
            logger.error(f"Unexpected generation failure for report {report_id}: {str(e)}")
            await cls._handle_failure(db, report_id, worker_id, generation_token, "GENERATION_FAILED")
            return False

    @classmethod
    async def _handle_failure(
        cls,
        db: AsyncSession,
        report_id: uuid.UUID,
        worker_id: str,
        generation_token: str,
        error_category: str
    ) -> None:
        """Handles failure safely without overwriting newer leases."""
        await db.rollback() # Revert any partial state

        update_stmt = (
            update(Report)
            .where(
                Report.id == report_id,
                Report.worker_id == worker_id,
                Report.generation_token == generation_token
            )
            .values(
                error_category=error_category
            )
        )
        await db.execute(update_stmt)

        # Log failure securely without tracebacks
        stmt = select(Report.organization_id).where(Report.id == report_id)
        org_id = (await db.execute(stmt)).scalar_one_or_none()

        if org_id:
            audit_log = AuditLog(
                id=uuid.uuid4(),
                organization_id=org_id,
                user_id=None,
                action=AuditAction.REPORT_GENERATION_FAILED,
                entity_type="Report",
                entity_id=str(report_id)
            )
            db.add(audit_log)

        await db.commit()
