import pytest
import asyncio
from unittest.mock import patch
from app.models.dependency import Dependency
from app.services.vulnerability_service import vulnerability_provider
from app.core.config import settings

@pytest.mark.asyncio
async def test_real_osv_e2e(seeded_session, sample_project):
    db_session = seeded_session

    # Create a mock artifact and scan
    from app.models.artifact import ProjectArtifact, ArtifactUploadStatus
    from app.models.scan import Scan, ScanStatus
    import uuid
    import datetime

    artifact = ProjectArtifact(
        project_id=sample_project.id,
        original_filename="requirements.txt",
        storage_key="test",
        size_bytes=10,
        content_hash="test",
        upload_status=ArtifactUploadStatus.READY
    )
    db_session.add(artifact)
    await db_session.flush()

    scan = Scan(
        project_id=sample_project.id,
        artifact_id=artifact.id,
        status=ScanStatus.RUNNING,
        started_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db_session.add(scan)
    await db_session.flush()

    # This test hits the REAL OSV API.
    # We must mock settings.ENVIRONMENT to not be "test"
    with patch("app.services.vulnerability_service.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"

        from app.models.ecosystem import PackageEcosystem
        from sqlalchemy import select
        eco = (await db_session.execute(select(PackageEcosystem).where(PackageEcosystem.name == "PyPI"))).scalar_one_or_none()

        dep1 = Dependency(
            project_id=sample_project.id,
            scan_id=scan.id,
            ecosystem_id=eco.id,
            package_name="requests",
            package_version="2.2.1",
            version_constraint="2.2.1",
            is_direct=True,
            is_transitive=False,
            manifest_file="requirements.txt"
        )
        dep1.ecosystem = eco

        # Insert dep to DB so it has an ID
        db_session.add(dep1)
        await db_session.flush()

        # Now call the orchestrator! This will hit OSV for requests==2.2.1
        count = await vulnerability_provider.match_vulnerabilities(db_session, scan.id, [dep1])

        # requests 2.2.1 has known vulnerabilities (e.g. CVE-2015-2296)
        assert count > 0

        # Check if the DB has the vulnerabilities
        from app.models.vulnerability import DependencyVulnerability
        from sqlalchemy import select

        stmt = select(DependencyVulnerability).where(DependencyVulnerability.scan_id == scan.id)
        findings = (await db_session.execute(stmt)).scalars().all()

        assert len(findings) > 0

        # Ensure we got real data
        finding = findings[0]
        assert finding.severity is not None
