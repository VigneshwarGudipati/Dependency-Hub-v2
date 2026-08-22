"""Tests for complete entity persistence and ORM relationship navigation."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AnalysisWorkspace,
    ArtifactEncryptionMetadata,
    ArtifactSourceType,
    ArtifactUploadStatus,
    AuditAction,
    AuditLog,
    Dependency,
    DependencyEdge,
    DependencyLicense,
    DependencyType,
    DependencyVersion,
    DependencyVulnerability,
    Finding,
    FindingResolutionStatus,
    FindingSeverity,
    FindingType,
    License,
    LicenseCategory,
    LicenseRiskLevel,
    MemberStatus,
    Organization,
    OrganizationMember,
    PackageEcosystem,
    Permission,
    Project,
    ProjectArtifact,
    ProjectType,
    ProjectVisibility,
    RefreshToken,
    RelationshipType,
    Role,
    RolePermission,
    Scan,
    ScanStatus,
    ScanType,
    SecurityPolicy,
    SeverityLevel,
    SystemRoleName,
    User,
    VersionStatus,
    Vulnerability,
    VulnerabilitySource,
)


@pytest.mark.asyncio
async def test_full_pipeline_persistence_and_relationships(
    seeded_session: AsyncSession,
    sample_user: User,
    sample_org: Organization,
    sample_project: Project,
):
    """Verify that all entities from User down to Findings and Logs persist correctly."""

    # 1. Project Artifact
    artifact = ProjectArtifact(
        project_id=sample_project.id,
        version_number=1,
        source_type=ArtifactSourceType.UPLOAD,
        original_filename="release-v1.0.0.zip",
        storage_provider="local",
        storage_key="artifacts/acme/project-1/v1.zip",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        size_bytes=102400,
        file_count=42,
        upload_status=ArtifactUploadStatus.READY,
        uploaded_by=sample_user.id,
        is_immutable=True,
    )
    seeded_session.add(artifact)
    await seeded_session.flush()
    assert artifact.id is not None

    # 2. Envelope Encryption Metadata
    enc_meta = ArtifactEncryptionMetadata(
        artifact_id=artifact.id,
        algorithm="AES-256-GCM",
        encryption_version="v1",
        key_reference="arn:aws:kms:us-east-1:123456789012:key/test-kek-uuid",
        initialization_vector="k4vY4+t3St1v==",
        authentication_tag="aUthT4gV4lu3==",
        encrypted_dek_reference="eNcRyPt3dD3k==b64",
        checksum="c4ca4238a0b923820dcc509a6f75849b2830f6587c67537b0dd64ff89650047c",
    )
    seeded_session.add(enc_meta)
    await seeded_session.flush()

    # 3. Ephemeral Analysis Workspace
    workspace = AnalysisWorkspace(
        artifact_id=artifact.id,
        workspace_identifier=f"ws-{uuid.uuid4().hex[:12]}",
        storage_reference="/tmp/sandboxes/ws-001",
    )
    seeded_session.add(workspace)
    await seeded_session.flush()

    # 4. Scan linked to the specific artifact snapshot
    scan = Scan(
        project_id=sample_project.id,
        artifact_id=artifact.id,
        initiated_by=sample_user.id,
        scan_type=ScanType.FULL,
        status=ScanStatus.COMPLETED,
        scanner_version="2.1.0",
        scanner_commit="abcdef1234567890",
        ruleset_version="2026.08",
        vulnerability_database_version="v2026-08-17",
        total_dependencies=2,
        direct_dependencies=1,
        transitive_dependencies=1,
        vulnerable_dependencies=1,
        configuration={"deep_scan": True},
        scan_metadata={"environment": "ci"},
    )
    seeded_session.add(scan)
    await seeded_session.flush()

    # Link workspace to scan
    workspace.scan_id = scan.id
    await seeded_session.flush()

    # 5. Ecosystem & Dependencies
    res = await seeded_session.execute(select(PackageEcosystem).where(PackageEcosystem.name == "npm"))
    npm_eco = res.scalar_one()

    express_dep = Dependency(
        project_id=sample_project.id,
        scan_id=scan.id,
        ecosystem_id=npm_eco.id,
        package_name="express",
        package_version="4.17.1",
        version_constraint="^4.17.1",
        dependency_type=DependencyType.RUNTIME,
        is_direct=True,
        is_transitive=False,
        package_manager="npm",
        manifest_file="package.json",
        lockfile="package-lock.json",
        license="MIT",
    )
    seeded_session.add(express_dep)
    await seeded_session.flush()

    qs_dep = Dependency(
        project_id=sample_project.id,
        scan_id=scan.id,
        ecosystem_id=npm_eco.id,
        package_name="qs",
        package_version="6.7.0",
        version_constraint="6.7.0",
        dependency_type=DependencyType.RUNTIME,
        is_direct=False,
        is_transitive=True,
        package_manager="npm",
    )
    seeded_session.add(qs_dep)
    await seeded_session.flush()

    # 6. Dependency Graph Edge (express -> qs)
    edge = DependencyEdge(
        scan_id=scan.id,
        parent_dependency_id=express_dep.id,
        child_dependency_id=qs_dep.id,
        relationship_type=RelationshipType.DIRECT,
        depth=1,
    )
    seeded_session.add(edge)
    await seeded_session.flush()

    # 7. Vulnerability & Dependency Finding
    vuln = Vulnerability(
        vulnerability_id=f"CVE-2022-24999-{uuid.uuid4().hex[:6]}",
        source=VulnerabilitySource.NVD,
        title="Prototype pollution in qs",
        description="qs vulnerable to prototype pollution via parsing logic",
        severity=SeverityLevel.HIGH,
        cvss_score=7.5,
        references=[{"url": "https://nvd.nist.gov/vuln/detail/CVE-2022-24999"}],
        affected_packages=[{"name": "qs", "ecosystem": "npm", "introduced": "6.0.0", "fixed": "6.7.3"}],
    )
    seeded_session.add(vuln)
    await seeded_session.flush()

    dep_vuln = DependencyVulnerability(
        scan_id=scan.id,
        dependency_id=qs_dep.id,
        vulnerability_id=vuln.id,
        severity=SeverityLevel.HIGH,
        cvss_score=7.5,
        status=FindingResolutionStatus.OPEN,
    )
    seeded_session.add(dep_vuln)
    await seeded_session.flush()

    # 8. License & Dependency Version Intelligence
    res_lic = await seeded_session.execute(select(License).where(License.spdx_identifier == "MIT"))
    mit_lic = res_lic.scalar_one()

    dep_lic = DependencyLicense(
        dependency_id=express_dep.id,
        license_id=mit_lic.id,
        detected_expression="MIT",
        confidence=1.0,
    )
    seeded_session.add(dep_lic)

    dep_ver = DependencyVersion(
        dependency_id=express_dep.id,
        current_version="4.17.1",
        latest_version="4.19.2",
        recommended_version="4.19.2",
        version_status=VersionStatus.OUTDATED,
    )
    seeded_session.add(dep_ver)
    await seeded_session.flush()

    # 9. Unified Finding for Dashboard Reporting
    finding = Finding(
        organization_id=sample_org.id,
        project_id=sample_project.id,
        scan_id=scan.id,
        dependency_id=qs_dep.id,
        vulnerability_id=vuln.id,
        finding_type=FindingType.VULNERABILITY,
        severity=FindingSeverity.HIGH,
        title="CVE-2022-24999: Prototype pollution in qs",
        description="High severity prototype pollution in transitive dependency qs@6.7.0",
    )
    seeded_session.add(finding)
    await seeded_session.flush()

    # 10. Security Policy
    policy = SecurityPolicy(
        organization_id=sample_org.id,
        name="Zero Critical Vulnerability Policy",
        description="Block builds with critical vulnerabilities or copyleft licenses",
        is_active=True,
        configuration={
            "max_critical_vulnerabilities": 0,
            "max_high_vulnerabilities": 2,
            "allow_copyleft": False,
        },
        created_by=sample_user.id,
    )
    seeded_session.add(policy)
    await seeded_session.flush()

    # 11. Refresh Token
    refresh_token = RefreshToken(
        user_id=sample_user.id,
        token_hash="sha256_hashed_token_value_random_12345",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    seeded_session.add(refresh_token)
    await seeded_session.flush()

    # 12. Audit Log
    audit = AuditLog(
        organization_id=sample_org.id,
        user_id=sample_user.id,
        action=AuditAction.SCAN_COMPLETED,
        entity_type="Scan",
        entity_id=str(scan.id),
        ip_address="127.0.0.1",
        user_agent="DependencyHub-CLI/1.0",
        new_values={"scan_id": str(scan.id), "status": "COMPLETED"},
    )
    seeded_session.add(audit)
    await seeded_session.flush()

    # 13. Verify Relationship Traversal
    stmt = (
        select(Project)
        .where(Project.id == sample_project.id)
        .options(
            selectinload(Project.artifacts).selectinload(ProjectArtifact.encryption_metadata),
            selectinload(Project.scans).selectinload(Scan.dependencies),
            selectinload(Project.findings),
        )
    )
    res_proj = await seeded_session.execute(stmt)
    loaded_project = res_proj.scalar_one()

    assert len(loaded_project.artifacts) == 1
    assert loaded_project.artifacts[0].encryption_metadata.algorithm == "AES-256-GCM"
    assert len(loaded_project.scans) == 1
    assert len(loaded_project.scans[0].dependencies) == 2
    assert len(loaded_project.findings) == 1
    assert loaded_project.findings[0].finding_type == FindingType.VULNERABILITY
