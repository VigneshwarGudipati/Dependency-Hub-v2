"""Centralized models export for Dependency Hub database schema."""

from app.models.base import Base, PrimaryKeyMixin, SoftDeleteMixin, TimestampMixin, utc_now
from app.models.user import User
from app.models.organization import MemberStatus, Organization, OrganizationMember
from app.models.role import Role, SystemRoleName
from app.models.permission import Permission, RolePermission
from app.models.project import Project, ProjectStatus, ProjectType, ProjectVisibility, RepositoryProvider
from app.models.artifact import ArtifactSourceType, ArtifactUploadStatus, ProjectArtifact
from app.models.encryption import ArtifactEncryptionMetadata
from app.models.workspace import AnalysisWorkspace, WorkspaceStatus
from app.models.scan import Scan, ScanStatus, ScanType
from app.models.ecosystem import PackageEcosystem
from app.models.dependency import Dependency, DependencyEdge, DependencyType, RelationshipType
from app.models.vulnerability import (
    DependencyVulnerability,
    FindingResolutionStatus,
    SeverityLevel,
    Vulnerability,
    VulnerabilitySource,
)
from app.models.license import (
    DependencyLicense,
    DependencyVersion,
    License,
    LicenseCategory,
    LicenseRiskLevel,
    VersionStatus,
)
from app.models.finding import Finding, FindingSeverity, FindingStatus, FindingType
from app.models.policy import SecurityPolicy
from app.models.audit import AuditAction, AuditLog
from app.models.refresh_token import RefreshToken
from app.models.registry_cache import RegistryCache
from app.models.report import (
    Report,
    ReportArtifact,
    ReportEncryptionMetadata,
    ReportFormat,
    ReportSnapshot,
    ReportStatus,
    ReportType,
)

__all__ = [
    # Base
    "Base",
    "PrimaryKeyMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "utc_now",
    # Auth & RBAC
    "User",
    "Organization",
    "OrganizationMember",
    "MemberStatus",
    "Role",
    "SystemRoleName",
    "Permission",
    "RolePermission",
    "RefreshToken",
    # Project & Artifacts
    "Project",
    "ProjectType",
    "RepositoryProvider",
    "ProjectVisibility",
    "ProjectStatus",
    "ProjectArtifact",
    "ArtifactSourceType",
    "ArtifactUploadStatus",
    "ArtifactEncryptionMetadata",
    "AnalysisWorkspace",
    "WorkspaceStatus",
    # Scans & Graph
    "Scan",
    "ScanType",
    "ScanStatus",
    "PackageEcosystem",
    "Dependency",
    "DependencyType",
    "DependencyEdge",
    "RelationshipType",
    # Security Intelligence & Findings
    "Vulnerability",
    "VulnerabilitySource",
    "SeverityLevel",
    "DependencyVulnerability",
    "FindingResolutionStatus",
    "License",
    "LicenseCategory",
    "LicenseRiskLevel",
    "DependencyLicense",
    "DependencyVersion",
    "VersionStatus",
    "Finding",
    "FindingType",
    "FindingSeverity",
    "FindingStatus",
    "SecurityPolicy",
    "AuditLog",
    "AuditAction",
    "RegistryCache",
    # Reporting
    "Report",
    "ReportArtifact",
    "ReportEncryptionMetadata",
    "ReportFormat",
    "ReportSnapshot",
    "ReportStatus",
    "ReportType",
]
