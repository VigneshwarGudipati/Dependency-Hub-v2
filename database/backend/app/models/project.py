"""Project model representing software repositories and projects."""

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.artifact import ProjectArtifact
    from app.models.scan import Scan
    from app.models.dependency import Dependency
    from app.models.finding import Finding


class ProjectType(str, enum.Enum):
    """Supported project classification types."""
    WEB = "WEB"
    MOBILE = "MOBILE"
    BACKEND = "BACKEND"
    DESKTOP = "DESKTOP"
    LIBRARY = "LIBRARY"
    MONOREPO = "MONOREPO"
    OTHER = "OTHER"


class RepositoryProvider(str, enum.Enum):
    """Repository hosting provider."""
    GITHUB = "GITHUB"
    GITLAB = "GITLAB"
    BITBUCKET = "BITBUCKET"
    LOCAL = "LOCAL"
    API = "API"
    OTHER = "OTHER"


class ProjectVisibility(str, enum.Enum):
    """Access visibility within tenant boundaries."""
    PRIVATE = "PRIVATE"
    ORGANIZATION = "ORGANIZATION"


class ProjectStatus(str, enum.Enum):
    """Operational lifecycle status of project."""
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DEPRECATED = "DEPRECATED"


class Project(Base, PrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Project entity representing an organization's analyzed codebase."""

    __tablename__ = "projects"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )
    repository_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    repository_provider: Mapped[RepositoryProvider] = mapped_column(
        Enum(RepositoryProvider, name="repository_provider_enum", native_enum=False),
        default=RepositoryProvider.OTHER,
        nullable=False,
    )
    default_branch: Mapped[str] = mapped_column(
        String(100),
        default="main",
        nullable=False,
    )
    project_type: Mapped[ProjectType] = mapped_column(
        Enum(ProjectType, name="project_type_enum", native_enum=False),
        default=ProjectType.OTHER,
        nullable=False,
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    visibility: Mapped[ProjectVisibility] = mapped_column(
        Enum(ProjectVisibility, name="project_visibility_enum", native_enum=False),
        default=ProjectVisibility.ORGANIZATION,
        nullable=False,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status_enum", native_enum=False),
        default=ProjectStatus.ACTIVE,
        nullable=False,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="projects",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    artifacts: Mapped[List["ProjectArtifact"]] = relationship(
        "ProjectArtifact",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    scans: Mapped[List["Scan"]] = relationship(
        "Scan",
        back_populates="project",
    )
    dependencies: Mapped[List["Dependency"]] = relationship(
        "Dependency",
        back_populates="project",
    )
    findings: Mapped[List["Finding"]] = relationship(
        "Finding",
        back_populates="project",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_org_project_slug"),
        Index("idx_projects_org_status", "organization_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Project {self.name} ({self.slug})>"
