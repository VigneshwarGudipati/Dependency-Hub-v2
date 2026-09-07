"""Report models for Security and Intelligence Reporting."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, UniqueConstraint, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID, BYTEA
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, SoftDeleteMixin, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.project import Project
    from app.models.scan import Scan
    from app.models.user import User


class ReportType(str, enum.Enum):
    """Types of reports that can be generated."""
    SECURITY_REPORT = "SECURITY_REPORT"
    PACKAGE_REPORT = "PACKAGE_REPORT"
    EXECUTIVE_REPORT = "EXECUTIVE_REPORT"
    COMPLIANCE_REPORT = "COMPLIANCE_REPORT"


class ReportFormat(str, enum.Enum):
    """Export formats for reports."""
    JSON = "JSON"
    HTML = "HTML"
    PDF = "PDF"
    CSV = "CSV"
    SARIF = "SARIF"


class ReportStatus(str, enum.Enum):
    """Lifecycle status of a report generation job."""
    QUEUED = "QUEUED"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"


class Report(Base, PrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Top-level metadata wrapper for a point-in-time scan report."""

    __tablename__ = "reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="The scan this report is based on. Nullable to allow reports to survive scan pruning.",
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type_enum", native_enum=False),
        nullable=False,
    )
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, name="report_format_enum", native_enum=False),
        nullable=False,
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status_enum", native_enum=False),
        default=ReportStatus.QUEUED,
        nullable=False,
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    generation_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the current or most recent generation attempt",
    )
    error_category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Safe categorical failure reason",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    worker_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Identity of the worker currently claiming the report",
    )
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the current worker lease expires",
    )
    generation_token: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        comment="Unique token for the current claim to prevent split-brain",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="reports",
    )
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="reports",
    )
    scan: Mapped[Optional["Scan"]] = relationship(
        "Scan",
        back_populates="reports",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    snapshot: Mapped[Optional["ReportSnapshot"]] = relationship(
        "ReportSnapshot",
        back_populates="report",
        uselist=False,
        cascade="all, delete-orphan",
    )
    artifacts: Mapped[List["ReportArtifact"]] = relationship(
        "ReportArtifact",
        back_populates="report",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "scan_id",
            "report_type",
            "format",
            name="uq_report_project_scan_type_format",
        ),
    )

    def __repr__(self) -> str:
        return f"<Report id={self.id} project={self.project_id} type={self.report_type} format={self.format}>"


class ReportSnapshot(Base, PrimaryKeyMixin):
    """Immutable point-in-time JSON representation of the scan data."""

    __tablename__ = "report_snapshots"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    snapshot_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
    )
    snapshot_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 checksum of the canonical plaintext JSON snapshot",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="snapshot",
    )

    def __repr__(self) -> str:
        return f"<ReportSnapshot report={self.report_id} schema={self.schema_version}>"


class ReportArtifact(Base, PrimaryKeyMixin):
    """Physical rendered file artifact stored with envelope encryption."""

    __tablename__ = "report_artifacts"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, name="report_format_enum", native_enum=False),
        nullable=False,
    )
    encrypted_data: Mapped[bytes] = mapped_column(
        BYTEA,
        nullable=False,
    )
    generation_token: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Tracks which generation attempt produced this artifact. Used for stale artifact reconciliation."
    )
    dek_ciphertext: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Fallback if not using dedicated encryption metadata table, but metadata table is preferred.",
    )
    artifact_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    artifact_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 checksum of the encrypted artifact blob",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="artifacts",
    )
    encryption_metadata: Mapped[Optional["ReportEncryptionMetadata"]] = relationship(
        "ReportEncryptionMetadata",
        back_populates="artifact",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("report_id", "format", name="uq_report_artifact_format"),
    )

    def __repr__(self) -> str:
        return f"<ReportArtifact report={self.report_id} format={self.format}>"


class ReportEncryptionMetadata(Base, PrimaryKeyMixin):
    """Envelope encryption metadata for report artifacts, mirroring ArtifactEncryptionMetadata."""

    __tablename__ = "report_encryption_metadata"

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_artifacts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    algorithm: Mapped[str] = mapped_column(
        String(50),
        default="AES-256-GCM",
        nullable=False,
    )
    encryption_version: Mapped[str] = mapped_column(
        String(20),
        default="v1",
        nullable=False,
    )
    key_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="External KMS Key Identifier / Vault Key Name",
    )
    initialization_vector: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Base64 encoded IV / Nonce",
    )
    authentication_tag: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Base64 encoded GCM authentication tag",
    )
    encrypted_dek_reference: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Base64 encoded encrypted Data Encryption Key",
    )
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 checksum of the ciphertext",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    artifact: Mapped["ReportArtifact"] = relationship(
        "ReportArtifact",
        back_populates="encryption_metadata",
    )

    def __repr__(self) -> str:
        return f"<ReportEncryptionMetadata artifact_id={self.artifact_id}>"
