"""Project Artifact model representing immutable snapshot uploads."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User
    from app.models.encryption import ArtifactEncryptionMetadata
    from app.models.workspace import AnalysisWorkspace
    from app.models.scan import Scan


class ArtifactSourceType(str, enum.Enum):
    """Source from which artifact was ingested."""
    UPLOAD = "UPLOAD"
    GIT = "GIT"
    GITHUB = "GITHUB"
    GITLAB = "GITLAB"
    BITBUCKET = "BITBUCKET"
    API = "API"


class ArtifactUploadStatus(str, enum.Enum):
    """Upload and processing state."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"
    DELETED = "DELETED"


class ProjectArtifact(Base, PrimaryKeyMixin):
    """Immutable project snapshot artifact."""

    __tablename__ = "project_artifacts"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    source_type: Mapped[ArtifactSourceType] = mapped_column(
        Enum(ArtifactSourceType, name="artifact_source_type_enum", native_enum=False),
        default=ArtifactSourceType.UPLOAD,
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    storage_provider: Mapped[str] = mapped_column(
        String(50),
        default="local",
        nullable=False,
    )
    storage_bucket: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    encrypted_storage_key: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),  # SHA-256 hex string
        nullable=False,
        index=True,
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    file_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    upload_status: Mapped[ArtifactUploadStatus] = mapped_column(
        Enum(ArtifactUploadStatus, name="artifact_upload_status_enum", native_enum=False),
        default=ArtifactUploadStatus.PENDING,
        nullable=False,
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_immutable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="artifacts",
    )
    uploader: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[uploaded_by],
    )
    encryption_metadata: Mapped[Optional["ArtifactEncryptionMetadata"]] = relationship(
        "ArtifactEncryptionMetadata",
        back_populates="artifact",
        uselist=False,
        cascade="all, delete-orphan",
    )
    workspaces: Mapped[List["AnalysisWorkspace"]] = relationship(
        "AnalysisWorkspace",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )
    scans: Mapped[List["Scan"]] = relationship(
        "Scan",
        back_populates="artifact",
    )

    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_project_artifact_version"),
        Index("idx_artifacts_project_created", "project_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ProjectArtifact id={self.id} project_id={self.project_id} v={self.version_number}>"
