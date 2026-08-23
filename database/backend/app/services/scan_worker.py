import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.scan import Scan, ScanStatus
from app.models.artifact import ProjectArtifact
from app.models.encryption import ArtifactEncryptionMetadata
from app.models.ecosystem import PackageEcosystem
from app.models.dependency import Dependency, DependencyType
from app.services.encryption_service import key_provider, decrypt_artifact
from app.services.parsers import get_parser
from app.services.vulnerability_service import vulnerability_provider


logger = logging.getLogger(__name__)


class ScanEngine:
    """The core engine that runs the analysis phases (extraction, parsing, matching)."""

    async def run(self, db: AsyncSession, scan: Scan) -> None:
        """Executes the analysis."""
        logger.info(f"ScanEngine running for scan {scan.id}")

        # 1. Load Artifact & Encryption Metadata
        stmt = select(ProjectArtifact).where(ProjectArtifact.id == scan.artifact_id)
        artifact = (await db.execute(stmt)).scalar_one_or_none()
        if not artifact:
            raise ValueError(f"Artifact {scan.artifact_id} not found")

        stmt = select(ArtifactEncryptionMetadata).where(ArtifactEncryptionMetadata.artifact_id == artifact.id)
        enc_meta = (await db.execute(stmt)).scalar_one_or_none()
        if not enc_meta:
            raise ValueError(f"Encryption metadata for {artifact.id} not found")

        # 2. Decrypt Artifact
        with open(artifact.storage_key, "rb") as f:
            ciphertext = f.read()

        dek = key_provider.decrypt_dek(enc_meta.encrypted_dek_reference)
        plaintext = decrypt_artifact(
            ciphertext=ciphertext,
            dek=dek,
            b64_nonce=enc_meta.initialization_vector,
            b64_tag=enc_meta.authentication_tag
        )

        # 3. Parse Manifest
        parser = get_parser(artifact.original_filename)
        if not parser:
            logger.info(f"No parser for {artifact.original_filename}")
            return

        content = plaintext.decode("utf-8")
        deps_info = parser.parse(content)

        # Determine ecosystem
        eco_name = "npm" if artifact.original_filename == "package.json" else "PyPI"
        stmt = select(PackageEcosystem).where(PackageEcosystem.name == eco_name)
        eco = (await db.execute(stmt)).scalar_one_or_none()
        if not eco:
            raise ValueError(f"Ecosystem {eco_name} not found")

        # 4. Save Dependencies
        scan.total_dependencies = len(deps_info)
        scan.direct_dependencies = len(deps_info)

        db_deps = []
        for d in deps_info:
            dep_record = Dependency(
                project_id=scan.project_id,
                scan_id=scan.id,
                ecosystem_id=eco.id,
                package_name=d.name,
                package_version=d.version_constraint or "*",
                version_constraint=d.version_constraint,
                dependency_type=DependencyType.DEVELOPMENT if d.is_dev else DependencyType.RUNTIME,
                is_direct=True,
                is_transitive=False,
                manifest_file=artifact.original_filename
            )
            db.add(dep_record)
            db_deps.append(dep_record)

        await db.flush() # Ensure dependency IDs are generated

        # 5. Match Vulnerabilities
        vuln_count = await vulnerability_provider.match_vulnerabilities(db, scan.id, db_deps)
        scan.vulnerable_dependencies = vuln_count

        logger.info(f"ScanEngine completed for scan {scan.id}, {len(deps_info)} dependencies parsed, {vuln_count} vulnerabilities found.")


class ScanWorker:
    """Worker abstraction that wraps the engine with state management and error handling."""

    def __init__(self, engine: ScanEngine):
        self.engine = engine

    async def execute_scan(self, scan_id: uuid.UUID) -> None:
        """
        Executes the scan process. This is typically run in a background task.
        Creates its own DB session so it doesn't share state with the HTTP request.
        """
        async with AsyncSessionLocal() as db:
            # Fetch scan
            stmt = select(Scan).where(Scan.id == scan_id)
            result = await db.execute(stmt)
            scan = result.scalar_one_or_none()

            if not scan:
                logger.error(f"Scan {scan_id} not found by worker")
                return

            if scan.status != ScanStatus.QUEUED:
                logger.warning(f"Scan {scan_id} is in state {scan.status}, skipping")
                return

            # Transition to RUNNING
            scan.status = ScanStatus.RUNNING
            scan.started_at = datetime.now(timezone.utc)
            await db.commit()

            try:
                # Run the engine
                await self.engine.run(db, scan)

                # Transition to COMPLETED
                scan.status = ScanStatus.COMPLETED
                scan.completed_at = datetime.now(timezone.utc)
                scan.duration_ms = int((scan.completed_at - scan.started_at).total_seconds() * 1000)
                await db.commit()

            except Exception as e:
                logger.exception(f"Scan {scan_id} failed: {str(e)}")

                if isinstance(e, RuntimeError) and str(e) == "PROVIDER_UNAVAILABLE":
                    scan.status = ScanStatus.PROVIDER_UNAVAILABLE
                    scan.error_message = "Vulnerability provider unavailable"
                else:
                    scan.status = ScanStatus.FAILED
                    scan.error_message = str(e)

                scan.completed_at = datetime.now(timezone.utc)
                await db.commit()

# Singleton instances
scan_engine = ScanEngine()
scan_worker = ScanWorker(scan_engine)
