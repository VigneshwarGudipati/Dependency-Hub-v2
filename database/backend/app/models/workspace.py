"""Analysis Workspace model representing ephemeral scanner environments."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.artifact import ProjectArtifact
    from app.models.scan import Scan


class WorkspaceStatus(str, enum.Enum):
    """Lifecycle status of temporary analysis workspace."""
    CREATED = "CREATED"
    EXTRACTING = "EXTRACTING"
    READY = "READY"
    ANALYZING = "ANALYZING"
    CLEANUP_PENDING = "CLEANUP_PENDING"
    DESTROYED = "DESTROYED"
    FAILED = "FAILED"


class AnalysisWorkspace(Base, PrimaryKeyMixin):
    """Temporary ephemeral workspace created for static scanner analysis.
    
    Security & Integrity Guarantee:
    Original encrypted artifacts remain read-only. Scanners operate solely
    within short-lived analysis workspaces that are scheduled for destruction.
    """

    __tablename__ = "analysis_workspaces"

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_identifier: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    storage_reference: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(WorkspaceStatus, name="workspace_status_enum", native_enum=False),
        default=WorkspaceStatus.CREATED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    destroyed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    artifact: Mapped["ProjectArtifact"] = relationship(
        "ProjectArtifact",
        back_populates="workspaces",
    )
    scan: Mapped[Optional["Scan"]] = relationship(
        "Scan",
        foreign_keys=[scan_id],
    )

    __table_args__ = (
        Index("idx_workspaces_status_expires", "status", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<AnalysisWorkspace {self.workspace_identifier} status={self.status}>"
