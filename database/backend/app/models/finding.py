"""Unified Findings model for dashboard-level security and dependency reporting."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.project import Project
    from app.models.scan import Scan
    from app.models.dependency import Dependency
    from app.models.vulnerability import Vulnerability
    from app.models.user import User


class FindingType(str, enum.Enum):
    """Categorization of unified finding."""
    VULNERABILITY = "VULNERABILITY"
    OUTDATED_DEPENDENCY = "OUTDATED_DEPENDENCY"
    LICENSE_RISK = "LICENSE_RISK"
    SECURITY_POLICY = "SECURITY_POLICY"
    CONFIGURATION = "CONFIGURATION"
    DEPENDENCY_CONFLICT = "DEPENDENCY_CONFLICT"
    UNKNOWN = "UNKNOWN"


class FindingSeverity(str, enum.Enum):
    """Severity classification for dashboard priority."""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class FindingStatus(str, enum.Enum):
    """Workflow state of a unified finding."""
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class Finding(Base, PrimaryKeyMixin, TimestampMixin):
    """Unified actionable finding aggregated across scans, dependencies, licenses, and policies."""

    __tablename__ = "findings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dependency_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    vulnerability_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vulnerabilities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    finding_type: Mapped[FindingType] = mapped_column(
        Enum(FindingType, name="finding_type_enum", native_enum=False),
        default=FindingType.UNKNOWN,
        nullable=False,
        index=True,
    )
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, name="finding_severity_enum", native_enum=False),
        default=FindingSeverity.UNKNOWN,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, name="unified_finding_status_enum", native_enum=False),
        default=FindingStatus.OPEN,
        nullable=False,
        index=True,
    )
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    finding_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="findings",
    )
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="findings",
    )
    scan: Mapped["Scan"] = relationship(
        "Scan",
        back_populates="findings",
    )
    dependency: Mapped[Optional["Dependency"]] = relationship(
        "Dependency",
        back_populates="findings",
    )
    vulnerability: Mapped[Optional["Vulnerability"]] = relationship(
        "Vulnerability",
        back_populates="unified_findings",
    )
    assignee: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_to],
    )

    __table_args__ = (
        Index("idx_findings_org_severity_status", "organization_id", "severity", "status"),
        Index("idx_findings_project_type", "project_id", "finding_type"),
    )

    def __repr__(self) -> str:
        return f"<Finding {self.title} [{self.severity}] status={self.status}>"
