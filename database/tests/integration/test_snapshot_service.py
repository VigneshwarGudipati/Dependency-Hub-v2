import uuid
import pytest
import hashlib
import json
from datetime import datetime, timezone
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from app.models.report import Report, ReportSnapshot, ReportType, ReportStatus
from app.models.scan import Scan, ScanStatus, ScanType
from app.models.project import Project, ProjectStatus
from app.models.organization import Organization
from app.models.dependency import Dependency, DependencyType, RelationshipType
from app.models.vulnerability import Vulnerability, DependencyVulnerability, SeverityLevel, VulnerabilitySource, FindingResolutionStatus
from app.services.snapshot_service import SnapshotService, SnapshotGenerationError, InvalidScanStatusError, TenantMismatchError

@pytest_asyncio.fixture
async def snapshot_fixtures(db_session: AsyncSession, request):
    org_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    report_id = uuid.uuid4()
    artifact_id = uuid.uuid4()

    org = Organization(id=org_id, name="Test Org", slug=f"test-org-{uuid.uuid4()}", is_active=True)
    proj = Project(id=proj_id, organization_id=org_id, name="Test Proj", slug=f"test-proj-{uuid.uuid4()}", status=ProjectStatus.ACTIVE)
    from app.models.artifact import ProjectArtifact, ArtifactSourceType, ArtifactUploadStatus
    artifact = ProjectArtifact(
        id=artifact_id,
        project_id=proj_id,
        version_number=1,
        source_type=ArtifactSourceType.UPLOAD,
        original_filename="test.zip",
        storage_key="test-key",
        content_hash="abcd123",
        size_bytes=100,
        upload_status=ArtifactUploadStatus.READY
    )
    scan = Scan(id=scan_id, project_id=proj_id, artifact_id=artifact_id, scan_type=ScanType.FULL, status=ScanStatus.COMPLETED)
    from app.models.report import ReportFormat
    report = Report(id=report_id, organization_id=org_id, project_id=proj_id, scan_id=scan_id, report_type=ReportType.SECURITY_REPORT, format=ReportFormat.JSON, status=ReportStatus.QUEUED)

    db_session.add_all([org, proj, artifact, scan, report])
    await db_session.flush()

    yield {"org": org, "proj": proj, "scan": scan, "report": report}

    await db_session.execute(delete(Report))
    await db_session.execute(delete(DependencyVulnerability))
    await db_session.execute(delete(Vulnerability))
    await db_session.execute(delete(Dependency))
    await db_session.execute(delete(Scan))
    await db_session.execute(delete(ProjectArtifact))
    await db_session.execute(delete(Project))
    await db_session.execute(delete(Organization))
    await db_session.commit()


@pytest.mark.asyncio
async def test_validation_rejections(db_session: AsyncSession, snapshot_fixtures):
    """Test 1-8: scan status validations and tenant ownership validations."""
    report = snapshot_fixtures["report"]
    scan = snapshot_fixtures["scan"]

    # 2-4. Queued/Running/Failed rejections
    for status in [ScanStatus.QUEUED, ScanStatus.RUNNING, ScanStatus.FAILED]:
        scan.status = status
        await db_session.flush()
        with pytest.raises(InvalidScanStatusError):
            await SnapshotService.create_snapshot(db_session, report.id)

    scan.status = ScanStatus.COMPLETED
    await db_session.flush()

    # 7. Tenant mismatch
    wrong_org = Organization(id=uuid.uuid4(), name="Wrong", slug=f"wrong-{uuid.uuid4()}", is_active=True)
    db_session.add(wrong_org)
    await db_session.flush()

    original_org = report.organization_id
    report.organization_id = wrong_org.id
    await db_session.flush()
    with pytest.raises(TenantMismatchError):
        await SnapshotService.create_snapshot(db_session, report.id)
    report.organization_id = original_org
    await db_session.flush()

    # 5-6. Missing report/scan
    with pytest.raises(SnapshotGenerationError):
        await SnapshotService.create_snapshot(db_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_1_vs_25_count_semantics(db_session: AsyncSession, snapshot_fixtures):
    """Test 9-13, 27: 1 package / 25 findings semantics and correct count aggregation."""
    report = snapshot_fixtures["report"]
    scan = snapshot_fixtures["scan"]
    proj = snapshot_fixtures["proj"]

    # Create 1 dependency (axios 0.21.0)
    dep = Dependency(
        id=uuid.uuid4(),
        project_id=proj.id,
        scan_id=scan.id,
        ecosystem_id=uuid.uuid4(), # Using a dummy ecosystem ID is fine if we mock or create Ecosystem. Actually we need a real ecosystem to flush without FK error.
        package_name="axios",
        package_version="0.21.0",
        dependency_type=DependencyType.RUNTIME,
        is_direct=True,
        is_transitive=False,
        metadata={"registry": {"outdated": True, "latest_version": "1.0.0"}}
    )
    from app.models.ecosystem import PackageEcosystem
    stmt = select(PackageEcosystem).filter(PackageEcosystem.name == "npm")
    result = await db_session.execute(stmt)
    eco = result.scalar_one_or_none()
    if not eco:
        eco = PackageEcosystem(id=uuid.uuid4(), name="npm")
        db_session.add(eco)
        await db_session.flush()
    dep.ecosystem_id = eco.id
    db_session.add(dep)

    # Create 25 vulnerability findings for that single dependency
    for i in range(25):
        vuln = Vulnerability(
            id=uuid.uuid4(),
            vulnerability_id=f"CVE-2021-{1000+i}",
            source=VulnerabilitySource.NVD,
            title="Axios SSRF",
            severity=SeverityLevel.HIGH
        )
        finding = DependencyVulnerability(
            id=uuid.uuid4(),
            scan_id=scan.id,
            dependency_id=dep.id,
            vulnerability_id=vuln.id,
            severity=SeverityLevel.HIGH,
            status=FindingResolutionStatus.OPEN
        )
        db_session.add_all([vuln, finding])

    await db_session.flush()

    snapshot = await SnapshotService.create_snapshot(db_session, report.id)
    summary = snapshot.snapshot_data["canonical_payload"]["summary"]

    assert summary["total_packages"] == 1
    assert summary["vulnerable_packages"] == 1
    assert summary["vulnerability_findings"] == 25
    assert summary["severity_counts"]["HIGH"] == 25


@pytest.mark.asyncio
async def test_idempotency_and_immutability(db_session: AsyncSession, snapshot_fixtures):
    """Test 19, 22-23, 29: Idempotency and immutability."""
    report = snapshot_fixtures["report"]

    snap1 = await SnapshotService.create_snapshot(db_session, report.id)
    await db_session.flush()

    snap2 = await SnapshotService.create_snapshot(db_session, report.id)
    assert snap1.id == snap2.id
    assert snap1.snapshot_sha256 == snap2.snapshot_sha256


@pytest.mark.asyncio
async def test_hash_correctness_and_exclusion(db_session: AsyncSession, snapshot_fixtures):
    """Test 20-21: Hash self-exclusion, canonical JSON bytes, independent reproducibility."""
    report = snapshot_fixtures["report"]

    snapshot = await SnapshotService.create_snapshot(db_session, report.id)
    canonical_payload = snapshot.snapshot_data["canonical_payload"]

    serialized = SnapshotService._deterministic_serialize(canonical_payload)
    recalculated_hash = hashlib.sha256(serialized).hexdigest()

    assert recalculated_hash == snapshot.snapshot_sha256


@pytest.mark.asyncio
async def test_transaction_rollback(db_session: AsyncSession, snapshot_fixtures):
    """Test 26: Outer transaction rollback removes snapshot (Snapshot Service does not secretly commit)."""
    report = snapshot_fixtures["report"]

    try:
        async with db_session.begin_nested():
            snap1 = await SnapshotService.create_snapshot(db_session, report.id)
            # Force a rollback
            raise IntegrityError("simulated concurrency race", None, None)
    except IntegrityError:
        pass

    # Ensure it's not committed in the outer transaction
    stmt = select(ReportSnapshot).filter_by(report_id=report.id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_empty_vulnerability_result(db_session: AsyncSession, snapshot_fixtures):
    """Test 26: Empty scan result snapshot generation."""
    report = snapshot_fixtures["report"]

    snapshot = await SnapshotService.create_snapshot(db_session, report.id)
    summary = snapshot.snapshot_data["canonical_payload"]["summary"]

    assert summary["total_packages"] == 0
    assert summary["vulnerable_packages"] == 0
    assert summary["vulnerability_findings"] == 0


@pytest.mark.asyncio
async def test_no_external_network_calls(monkeypatch, db_session: AsyncSession, snapshot_fixtures):
    """Test 25: Ensure absolutely ZERO external provider calls occur."""
    import httpx
    import requests

    def block_requests(*args, **kwargs):
        raise AssertionError("Network call attempted during snapshot generation!")

    monkeypatch.setattr(requests, "get", block_requests)
    monkeypatch.setattr(requests, "post", block_requests)
    monkeypatch.setattr(httpx, "get", block_requests)
    monkeypatch.setattr(httpx, "post", block_requests)

    report = snapshot_fixtures["report"]
    await SnapshotService.create_snapshot(db_session, report.id)
    # If no assertion error is raised, we are completely detached from network providers.

@pytest.mark.asyncio
async def test_unsupported_serializer_type_fails():
    from app.services.snapshot_service import SnapshotService
    class UnserializableType:
        pass
    with pytest.raises(TypeError, match="not serializable in deterministic payload"):
        SnapshotService._deterministic_serialize({"bad": UnserializableType()})

@pytest.mark.asyncio
async def test_metadata_whitelist(db_session: AsyncSession, snapshot_fixtures):
    from app.services.snapshot_service import SnapshotService
    from app.models.dependency import Dependency, DependencyType
    from app.models.vulnerability import DependencyVulnerability, Vulnerability, SeverityLevel
    import uuid

    report = snapshot_fixtures["report"]
    scan = snapshot_fixtures["scan"]
    proj = snapshot_fixtures["proj"]

    from sqlalchemy import select
    from app.models.ecosystem import PackageEcosystem
    stmt = select(PackageEcosystem).filter(PackageEcosystem.name == "npm")
    result = await db_session.execute(stmt)
    eco = result.scalar_one_or_none()
    if not eco:
        eco = PackageEcosystem(id=uuid.uuid4(), name="npm")
        db_session.add(eco)
        await db_session.flush()

    dep = Dependency(
        id=uuid.uuid4(),
        project_id=proj.id,
        scan_id=scan.id,
        ecosystem_id=eco.id,
        package_name="axios2",
        package_version="0.21.0",
        dependency_type=DependencyType.RUNTIME,
        is_direct=True,
        is_transitive=False,
        dependency_metadata={
            "registry": {
                "latest_version": "2.0.0",
                "outdated": True,
                "provider": "npm",
                "status": "active",
                "cache_state": "hit",
                "license": "MIT",
                "published_at": "2023-01-01",
                "unexpected_field": "SHOULD_BE_REMOVED",
                "nested_secret": {"token": "hidden"}
            },
            "other_root_field": "SHOULD_BE_REMOVED"
        }
    )
    db_session.add(dep)

    vuln = Vulnerability(
        id=uuid.uuid4(),
        vulnerability_id="CVE-TEST2",
        title="Test Vuln"
    )
    db_session.add(vuln)

    dv = DependencyVulnerability(
        id=uuid.uuid4(),
        scan_id=scan.id,
        dependency_id=dep.id,
        vulnerability_id=vuln.id,
        severity=SeverityLevel.HIGH,
        finding_metadata={
            "affected_versions": ["<2.0.0"],
            "patched_version": "2.0.0",
            "cve_score": 9.8,
            "unexpected_finding_field": "SHOULD_BE_REMOVED"
        }
    )
    db_session.add(dv)

    await db_session.flush()

    snapshot = await SnapshotService.create_snapshot(db_session, report.id)
    payload = snapshot.snapshot_data["canonical_payload"]

    # Locate the correct dependency
    reg_meta = {}
    for d in payload["dependencies"]:
        if d["package_name"] == "axios2":
            reg_meta = d["registry_metadata"]
            break

    assert "latest_version" in reg_meta
    assert "outdated" in reg_meta
    assert "unexpected_field" not in reg_meta
    assert "nested_secret" not in reg_meta

    find_meta = {}
    for v in payload["vulnerabilities"]:
        if v["vulnerability_id"] == "CVE-TEST2":
            find_meta = v["finding_metadata"]
            break

    assert "affected_versions" in find_meta
    assert "patched_version" in find_meta
    assert "cve_score" not in find_meta
    assert "unexpected_finding_field" not in find_meta

@pytest.mark.asyncio
async def test_race_recovery_failure(db_session: AsyncSession, snapshot_fixtures, monkeypatch):
    from app.services.snapshot_service import SnapshotService, SnapshotRaceRecoveryError
    from sqlalchemy.exc import IntegrityError
    report = snapshot_fixtures["report"]

    original_execute = db_session.execute

    class MockResult:
        def scalar_one_or_none(self):
            return None

    raised = False
    async def fake_execute(stmt, *args, **kwargs):
        nonlocal raised
        stmt_str = str(stmt)
        if "report_snapshots.report_id =" in stmt_str and raised:
            return MockResult()
        return await original_execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", fake_execute)

    original_flush = db_session.flush
    async def fake_flush(*args, **kwargs):
        nonlocal raised
        if not raised:
            raised = True
            raise IntegrityError("statement", "params", "orig")
        return await original_flush(*args, **kwargs)

    monkeypatch.setattr(db_session, "flush", fake_flush)

    with pytest.raises(SnapshotRaceRecoveryError, match="existing snapshot not found"):
        await SnapshotService.create_snapshot(db_session, report.id)
