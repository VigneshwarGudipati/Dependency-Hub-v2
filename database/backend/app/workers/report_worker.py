"""Durable Background Worker for Report Generation."""

import asyncio
import logging
import socket
import sys
import uuid
from datetime import timedelta

from sqlalchemy import select, or_, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.models.report import Report, ReportStatus
from app.models.organization import Organization
from app.models.audit import AuditLog, AuditAction
from app.models.base import utc_now
from app.services.reporting.report_generation_service import ReportGenerationService

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
LEASE_DURATION_MINUTES = 10
MAX_ORG_CONCURRENCY = 5


class ReportWorker:
    def __init__(self):
        self.worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.is_running = False

    async def claim_job(self, db: AsyncSession) -> tuple[Report | None, str | None]:
        """Atomically claim a report for generation using FOR UPDATE SKIP LOCKED."""
        now = utc_now()

        # 1. Find a candidate
        candidate_stmt = select(Report).where(
            or_(
                Report.status == ReportStatus.QUEUED,
                and_(
                    Report.status == ReportStatus.GENERATING,
                    Report.lease_expires_at < now,
                    Report.attempt_count < MAX_ATTEMPTS
                )
            )
        ).order_by(Report.created_at.asc()).limit(1).with_for_update(skip_locked=True)

        candidate = (await db.execute(candidate_stmt)).scalar_one_or_none()
        if not candidate:
            return None, None

        # 2. Lock the Organization to serialize claims and enforce concurrency limits safely
        # Using nowait=True so we don't block if another worker is claiming for this org.
        org_stmt = select(Organization).where(Organization.id == candidate.organization_id).with_for_update(nowait=True)
        try:
            org = (await db.execute(org_stmt)).scalar_one_or_none()
            if not org:
                await db.rollback()
                return None, None
        except Exception:
            # Lock could not be acquired immediately. Skip and try again later.
            await db.rollback()
            return None, None

        # 3. Enforce Organization Concurrency Cap
        count_stmt = select(func.count(Report.id)).where(
            Report.organization_id == candidate.organization_id,
            Report.status == ReportStatus.GENERATING,
            Report.lease_expires_at > now
        )
        active_count = (await db.execute(count_stmt)).scalar_one()

        if active_count >= MAX_ORG_CONCURRENCY:
            # Cap reached. We cannot claim this candidate.
            await db.rollback()
            return None, None

        # 4. Perform atomic claim
        generation_token = str(uuid.uuid4())
        candidate.status = ReportStatus.GENERATING
        candidate.worker_id = self.worker_id
        candidate.generation_token = generation_token
        candidate.generation_started_at = now
        candidate.lease_expires_at = now + timedelta(minutes=LEASE_DURATION_MINUTES)
        candidate.attempt_count += 1

        # Ensure it is expunged after commit so we can pass it to other sessions if needed,
        # but since we run the service in a fresh session or same session, we will just pass IDs.
        report_id = candidate.id

        # Log Audit Action (worker acting as system)
        audit_log = AuditLog(
            id=uuid.uuid4(),
            organization_id=candidate.organization_id,
            user_id=None,
            action=AuditAction.REPORT_GENERATION_STARTED,
            entity_type="Report",
            entity_id=str(report_id),
            audit_metadata={"worker_id": self.worker_id, "attempt": candidate.attempt_count}
        )
        db.add(audit_log)

        await db.commit()
        return candidate, generation_token

    async def recover_permanent_failures(self, db: AsyncSession):
        """Sweep for GENERATING reports that have expired and exhausted attempts."""
        now = utc_now()
        stale_stmt = select(Report).where(
            Report.status == ReportStatus.GENERATING,
            Report.lease_expires_at < now,
            Report.attempt_count >= MAX_ATTEMPTS
        ).limit(50).with_for_update(skip_locked=True)

        stale_reports = (await db.execute(stale_stmt)).scalars().all()

        for report in stale_reports:
            logger.warning(f"Report {report.id} exhausted {MAX_ATTEMPTS} attempts and is permanently FAILED.")
            report.status = ReportStatus.FAILED
            report.error_category = "JOB_TIMEOUT"

            audit_log = AuditLog(
                id=uuid.uuid4(),
                organization_id=report.organization_id,
                user_id=None,
                action=AuditAction.REPORT_GENERATION_FAILED,
                entity_type="Report",
                entity_id=str(report.id),
                audit_metadata={"reason": "MAX_ATTEMPTS_EXHAUSTED"}
            )
            db.add(audit_log)

        if stale_reports:
            await db.commit()
        else:
            await db.rollback()

    async def run(self):
        """Main worker loop."""
        self.is_running = True
        logger.info(f"Started ReportWorker {self.worker_id}")

        while self.is_running:
            try:
                async with AsyncSessionLocal() as db:
                    # 1. Recover permanently failed jobs to prevent infinite GENERATING loops
                    await self.recover_permanent_failures(db)

                    # 2. Try to claim a job
                    report, generation_token = await self.claim_job(db)

                if report and generation_token:
                    logger.info(f"Worker {self.worker_id} claimed report {report.id} (Attempt {report.attempt_count})")

                    # 3. Execute job in a fresh session to ensure clean transaction state
                    async with AsyncSessionLocal() as exec_db:
                        success = await ReportGenerationService.generate_report(
                            exec_db,
                            report.id,
                            self.worker_id,
                            generation_token
                        )
                        if success:
                            logger.info(f"Successfully generated report {report.id}")
                        else:
                            logger.warning(f"Failed to generate report {report.id}")

                else:
                    # Exponential backoff or sleep when no jobs
                    await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Worker {self.worker_id} encountered critical error: {e}")
                await asyncio.sleep(5)

    def stop(self):
        """Graceful shutdown signal."""
        logger.info(f"Worker {self.worker_id} stopping...")
        self.is_running = False


async def async_main():
    worker = ReportWorker()
    try:
        await worker.run()
    except KeyboardInterrupt:
        worker.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(async_main())
