import json
import hashlib
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.report import Report, ReportSnapshot, ReportStatus
from app.models.scan import Scan, ScanStatus
from app.models.project import Project
from app.models.dependency import Dependency, DependencyType
from app.models.vulnerability import DependencyVulnerability, SeverityLevel

logger = logging.getLogger(__name__)


class SnapshotGenerationError(Exception):
    """Base error for snapshot generation failures."""
    pass


class InvalidScanStatusError(SnapshotGenerationError):
    """Scan is not in a completed state."""
    pass


class TenantMismatchError(SnapshotGenerationError):
    """Tenant/Ownership validation failed."""
    pass


class SnapshotRaceRecoveryError(SnapshotGenerationError):
    """Concurrent race recovery failed."""
    pass


class SnapshotService:
    """Service to generate deterministic, immutable snapshots of scan data for reports."""

    SCHEMA_VERSION = "1.0.0"
    GENERATOR_VERSION = "1.0.0"

    @staticmethod
    def _deterministic_serialize(payload: dict) -> bytes:
        import uuid
        import enum
        from datetime import datetime

        def strict_serializer(obj):
            if isinstance(obj, uuid.UUID):
                return str(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, enum.Enum):
                return obj.name if hasattr(obj, 'name') else str(obj)
            raise TypeError(f"Type {type(obj)} not serializable in deterministic payload")

        return json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
            default=strict_serializer
        ).encode('utf-8')

    @classmethod
    def _build_canonical_payload(cls, scan: Scan) -> Dict[str, Any]:
        """Construct the canonical hashed payload."""

        # Sort dependencies predictably
        sorted_deps = sorted(
            scan.dependencies,
            key=lambda d: (d.ecosystem.name if d.ecosystem else "", d.package_name, d.package_version, str(d.id))
        )

        # Count semantics logic (pure iteration, no N+1 query since eager loaded)
        vulnerable_packages_set = set()
        vulnerability_findings_count = 0
        critical = 0
        high = 0
        medium = 0
        low = 0

        dependencies_payload = []
        for dep in sorted_deps:
            # Registry semantics explicitly whitelisted
            registry_meta = dep.dependency_metadata.get("registry", {})
            allowed_registry_fields = {"latest_version", "outdated", "provider", "status", "cache_state", "license", "published_at"}
            safe_registry_meta = {k: v for k, v in registry_meta.items() if k in allowed_registry_fields}

            dependencies_payload.append({
                "id": str(dep.id),
                "package_name": dep.package_name,
                "ecosystem": dep.ecosystem.name if dep.ecosystem else "UNKNOWN",
                "package_version": dep.package_version,
                "version_constraint": dep.version_constraint,
                "dependency_type": dep.dependency_type.name if hasattr(dep.dependency_type, 'name') else str(dep.dependency_type),
                "is_direct": dep.is_direct,
                "registry_metadata": safe_registry_meta
            })

        # Vulnerabilities
        vulnerabilities_payload = []
        sorted_vulns = sorted(
            scan.vulnerability_findings,
            key=lambda dv: (str(dv.dependency_id), str(dv.vulnerability_id))
        )

        for dv in sorted_vulns:
            vulnerable_packages_set.add(dv.dependency_id)
            vulnerability_findings_count += 1

            sev = dv.severity.name if hasattr(dv.severity, 'name') else str(dv.severity)
            if sev == "CRITICAL": critical += 1
            elif sev == "HIGH": high += 1
            elif sev == "MEDIUM": medium += 1
            elif sev == "LOW": low += 1

            vuln_obj = dv.vulnerability

            allowed_finding_fields = {"affected_versions", "patched_version"}
            safe_finding_meta = {k: v for k, v in dv.finding_metadata.items() if k in allowed_finding_fields} if dv.finding_metadata else {}

            vulnerabilities_payload.append({
                "dependency_id": str(dv.dependency_id),
                "vulnerability_id": vuln_obj.vulnerability_id if vuln_obj else "UNKNOWN",
                "title": vuln_obj.title if vuln_obj else "UNKNOWN",
                "severity": sev,
                "finding_metadata": safe_finding_meta,
            })

        payload = {
            "project": {
                "id": str(scan.project_id),
                "name": scan.project.name if scan.project else "UNKNOWN",
            },
            "scan": {
                "id": str(scan.id),
                "scan_type": scan.scan_type.name if hasattr(scan.scan_type, 'name') else str(scan.scan_type),
                "started_at": scan.started_at.isoformat() if scan.started_at else None,
                "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
                "scanner_version": scan.scanner_version,
            },
            "summary": {
                "total_packages": len(sorted_deps),
                "vulnerable_packages": len(vulnerable_packages_set),
                "vulnerability_findings": vulnerability_findings_count,
                "severity_counts": {
                    "CRITICAL": critical,
                    "HIGH": high,
                    "MEDIUM": medium,
                    "LOW": low,
                }
            },
            "dependencies": dependencies_payload,
            "vulnerabilities": vulnerabilities_payload
        }
        return payload

    @classmethod
    async def create_snapshot(cls, db: AsyncSession, report_id: uuid.UUID) -> ReportSnapshot:
        """
        Create a canonical deterministic snapshot for a completed scan via a report.
        Handles races safely and returns existing snapshot if already created.
        Does NOT execute a full db.commit().
        """
        logger.info(f"snapshot_generation_started report_id={report_id}")

        # 1. Fetch Report and validate tenant/relationships
        stmt = select(Report).options(
            selectinload(Report.project),
            selectinload(Report.scan),
            selectinload(Report.snapshot)
        ).filter(Report.id == report_id)
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()

        if not report:
            logger.error(f"snapshot_generation_failed report_id={report_id} reason=report_not_found")
            raise SnapshotGenerationError(f"Report {report_id} not found.")

        # 2. Idempotency Check
        if report.snapshot:
            logger.info(f"snapshot_generation_completed report_id={report_id} reason=existing_snapshot_returned")
            return report.snapshot

        if not report.scan:
            logger.error(f"snapshot_generation_failed report_id={report_id} reason=scan_missing")
            raise SnapshotGenerationError(f"Report {report_id} has no associated scan.")

        # 3. Tenant Validation
        if report.organization_id != report.project.organization_id:
            logger.error(f"snapshot_generation_failed report_id={report_id} reason=tenant_mismatch")
            raise TenantMismatchError("Report organization does not match Project organization.")

        if report.project_id != report.scan.project_id:
            logger.error(f"snapshot_generation_failed report_id={report_id} reason=project_mismatch")
            raise TenantMismatchError("Report project does not match Scan project.")

        # 4. Scan Eligibility
        if report.scan.status != ScanStatus.COMPLETED:
            logger.error(f"snapshot_generation_failed report_id={report_id} reason=scan_not_completed")
            raise InvalidScanStatusError(f"Cannot snapshot scan in state: {report.scan.status}")

        # 5. Fetch fully hydrated scan to build canonical payload (prevent N+1)
        scan_stmt = select(Scan).options(
            selectinload(Scan.project),
            selectinload(Scan.dependencies).selectinload(Dependency.ecosystem),
            selectinload(Scan.vulnerability_findings).joinedload(DependencyVulnerability.vulnerability)
        ).filter(Scan.id == report.scan_id)
        scan_result = await db.execute(scan_stmt)
        scan = scan_result.scalar_one()

        # 6. Build canonical payload & Hash
        canonical_payload = cls._build_canonical_payload(scan)
        serialized_bytes = cls._deterministic_serialize(canonical_payload)
        snapshot_sha256 = hashlib.sha256(serialized_bytes).hexdigest()

        # 7. Envelope Assembly (Metadata separated from hashed canonical bytes)
        generation_metadata = {
            "report_id": str(report.id),
            "scan_id": str(scan.id),
            "project_id": str(scan.project_id),
            "organization_id": str(report.organization_id),
            "schema_version": cls.SCHEMA_VERSION,
            "generator_version": cls.GENERATOR_VERSION,
            "snapshot_sha256": snapshot_sha256,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        envelope = {
            "metadata": generation_metadata,
            "canonical_payload": canonical_payload
        }

        # 8. Persistence with concurrent race safety
        new_snapshot = ReportSnapshot(
            report_id=report.id,
            snapshot_data=envelope,
            schema_version=cls.SCHEMA_VERSION,
            snapshot_sha256=snapshot_sha256
        )

        try:
            # We use a savepoint so that an integrity error does not invalidate the outer transaction
            async with db.begin_nested():
                db.add(new_snapshot)
                await db.flush()
        except IntegrityError:
            # Concurrent race caught: another worker already created it.
            logger.info(f"snapshot_generation_completed report_id={report_id} reason=concurrent_race_won_by_other")
            # The nested transaction is rolled back, outer transaction remains valid.
            existing_stmt = select(ReportSnapshot).filter(ReportSnapshot.report_id == report_id)
            existing_result = await db.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()
            if not existing:
                raise SnapshotRaceRecoveryError(f"Concurrent race won but existing snapshot not found for report {report_id}")
            return existing

        logger.info(f"snapshot_generation_completed report_id={report_id}")
        return new_snapshot
