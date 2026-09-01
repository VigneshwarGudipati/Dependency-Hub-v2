"""Scan model representing reproducible dependency and vulnerability analyses."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.artifact import ProjectArtifact
    from app.models.user import User
    from app.models.dependency import Dependency, DependencyEdge
    from app.models.vulnerability import DependencyVulnerability
    from app.models.finding import Finding
    from app.models.report import Report


class ScanType(str, enum.Enum):
    """Scan execution mode and scope."""
    FULL = "FULL"
    QUICK = "QUICK"
    SECURITY = "SECURITY"
    DEPENDENCY = "DEPENDENCY"
    LICENSE = "LICENSE"
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"


class ScanStatus(str, enum.Enum):
    """Scan state machine status."""
    QUEUED = "QUEUED"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"


class Scan(Base, PrimaryKeyMixin, TimestampMixin):
    """Scan record capturing immutable results linked to a specific artifact snapshot."""

    __tablename__ = "scans"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_artifacts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    initiated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    scan_type: Mapped[ScanType] = mapped_column(
        Enum(ScanType, name="scan_type_enum", native_enum=False),
        default=ScanType.FULL,
        nullable=False,
    )
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status_enum", native_enum=False, length=50),
        default=ScanStatus.QUEUED,
        nullable=False,
        index=True,
    )

    # Scanner Reproducibility Provenance
    scanner_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1.0.0",
    )
    scanner_commit: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
    )
    ruleset_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    vulnerability_database_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Execution timings & metrics
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Summary Metrics
    total_dependencies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    direct_dependencies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transitive_dependencies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vulnerable_dependencies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outdated_dependencies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    license_issues: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    configuration: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    # Python attribute scan_metadata maps to DB column 'metadata' to avoid SQLAlchemy Base.metadata collision
    scan_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="scans",
    )
    artifact: Mapped["ProjectArtifact"] = relationship(
        "ProjectArtifact",
        back_populates="scans",
    )
    initiator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[initiated_by],
    )
    dependencies: Mapped[List["Dependency"]] = relationship(
        "Dependency",
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    dependency_edges: Mapped[List["DependencyEdge"]] = relationship(
        "DependencyEdge",
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    vulnerability_findings: Mapped[List["DependencyVulnerability"]] = relationship(
        "DependencyVulnerability",
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    findings: Mapped[List["Finding"]] = relationship(
        "Finding",
        back_populates="scan",
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        back_populates="scan",
    )

    __table_args__ = (
        Index("idx_scans_project_created", "project_id", "created_at"),
        Index("idx_scans_artifact_status", "artifact_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Scan id={self.id} project_id={self.project_id} status={self.status}>"
