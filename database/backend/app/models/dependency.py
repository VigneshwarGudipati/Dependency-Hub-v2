"""Dependency and Dependency Graph models."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.scan import Scan
    from app.models.ecosystem import PackageEcosystem
    from app.models.vulnerability import DependencyVulnerability
    from app.models.license import DependencyLicense, DependencyVersion
    from app.models.finding import Finding


class DependencyType(str, enum.Enum):
    """Classification of dependency scope."""
    RUNTIME = "RUNTIME"
    DEVELOPMENT = "DEVELOPMENT"
    OPTIONAL = "OPTIONAL"
    PEER = "PEER"
    BUILD = "BUILD"
    UNKNOWN = "UNKNOWN"


class RelationshipType(str, enum.Enum):
    """Graph edge relationship type."""
    DIRECT = "DIRECT"
    TRANSITIVE = "TRANSITIVE"
    PEER = "PEER"
    OPTIONAL = "OPTIONAL"
    DEV = "DEV"


class Dependency(Base, PrimaryKeyMixin):
    """Software package dependency detected within a scan."""

    __tablename__ = "dependencies"

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
    ecosystem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("package_ecosystems.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    package_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    package_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    version_constraint: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    dependency_type: Mapped[DependencyType] = mapped_column(
        Enum(DependencyType, name="dependency_type_enum", native_enum=False),
        default=DependencyType.RUNTIME,
        nullable=False,
    )
    is_direct: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_transitive: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    package_manager: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    manifest_file: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    lockfile: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    license: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    dependency_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
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
        back_populates="dependencies",
    )
    scan: Mapped["Scan"] = relationship(
        "Scan",
        back_populates="dependencies",
    )
    ecosystem: Mapped["PackageEcosystem"] = relationship(
        "PackageEcosystem",
        back_populates="dependencies",
    )
    outgoing_edges: Mapped[List["DependencyEdge"]] = relationship(
        "DependencyEdge",
        foreign_keys="DependencyEdge.parent_dependency_id",
        back_populates="parent_dependency",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[List["DependencyEdge"]] = relationship(
        "DependencyEdge",
        foreign_keys="DependencyEdge.child_dependency_id",
        back_populates="child_dependency",
        cascade="all, delete-orphan",
    )
    vulnerabilities: Mapped[List["DependencyVulnerability"]] = relationship(
        "DependencyVulnerability",
        back_populates="dependency",
        cascade="all, delete-orphan",
    )
    licenses: Mapped[List["DependencyLicense"]] = relationship(
        "DependencyLicense",
        back_populates="dependency",
        cascade="all, delete-orphan",
    )
    version_info: Mapped[Optional["DependencyVersion"]] = relationship(
        "DependencyVersion",
        back_populates="dependency",
        uselist=False,
        cascade="all, delete-orphan",
    )
    findings: Mapped[List["Finding"]] = relationship(
        "Finding",
        back_populates="dependency",
    )

    __table_args__ = (
        UniqueConstraint("scan_id", "ecosystem_id", "package_name", "package_version", name="uq_scan_pkg_version"),
        Index("idx_dependencies_scan_pkg", "scan_id", "package_name"),
    )

    def __repr__(self) -> str:
        return f"<Dependency {self.package_name}@{self.package_version}>"


class DependencyEdge(Base, PrimaryKeyMixin):
    """Directed graph edge representing parent-child dependency relationships."""

    __tablename__ = "dependency_edges"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_dependency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    child_dependency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType, name="relationship_type_enum", native_enum=False),
        default=RelationshipType.DIRECT,
        nullable=False,
    )
    depth: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    edge_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    scan: Mapped["Scan"] = relationship(
        "Scan",
        back_populates="dependency_edges",
    )
    parent_dependency: Mapped["Dependency"] = relationship(
        "Dependency",
        foreign_keys=[parent_dependency_id],
        back_populates="outgoing_edges",
    )
    child_dependency: Mapped["Dependency"] = relationship(
        "Dependency",
        foreign_keys=[child_dependency_id],
        back_populates="incoming_edges",
    )

    __table_args__ = (
        UniqueConstraint("scan_id", "parent_dependency_id", "child_dependency_id", name="uq_dependency_edge"),
        Index("idx_dep_edges_parent_child", "parent_dependency_id", "child_dependency_id"),
    )

    def __repr__(self) -> str:
        return f"<DependencyEdge {self.parent_dependency_id} -> {self.child_dependency_id}>"
