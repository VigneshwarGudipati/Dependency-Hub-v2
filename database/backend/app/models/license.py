"""License, Dependency License, and Version Intelligence models."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.dependency import Dependency


class LicenseCategory(str, enum.Enum):
    """SPDX and open source license categories."""
    PERMISSIVE = "PERMISSIVE"
    COPYLEFT = "COPYLEFT"
    WEAK_COPYLEFT = "WEAK_COPYLEFT"
    PROPRIETARY = "PROPRIETARY"
    UNKNOWN = "UNKNOWN"


class LicenseRiskLevel(str, enum.Enum):
    """Compliance risk rating."""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class VersionStatus(str, enum.Enum):
    """Package obsolescence and update classification."""
    UP_TO_DATE = "UP_TO_DATE"
    OUTDATED = "OUTDATED"
    MAJOR_UPDATE = "MAJOR_UPDATE"
    MINOR_UPDATE = "MINOR_UPDATE"
    PATCH_UPDATE = "PATCH_UPDATE"
    UNKNOWN = "UNKNOWN"


class License(Base, PrimaryKeyMixin, TimestampMixin):
    """Normalized license catalog entity (e.g. MIT, Apache-2.0, GPL-3.0)."""

    __tablename__ = "licenses"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    spdx_identifier: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    category: Mapped[LicenseCategory] = mapped_column(
        Enum(LicenseCategory, name="license_category_enum", native_enum=False),
        default=LicenseCategory.UNKNOWN,
        nullable=False,
    )
    risk_level: Mapped[LicenseRiskLevel] = mapped_column(
        Enum(LicenseRiskLevel, name="license_risk_level_enum", native_enum=False),
        default=LicenseRiskLevel.UNKNOWN,
        nullable=False,
    )
    license_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    dependency_licenses: Mapped[List["DependencyLicense"]] = relationship(
        "DependencyLicense",
        back_populates="license",
    )

    def __repr__(self) -> str:
        return f"<License {self.spdx_identifier} ({self.category})>"


class DependencyLicense(Base, PrimaryKeyMixin):
    """Many-to-many join model between Dependency and License detections."""

    __tablename__ = "dependency_licenses"

    dependency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    license_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("licenses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    detected_expression: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    dependency: Mapped["Dependency"] = relationship(
        "Dependency",
        back_populates="licenses",
    )
    license: Mapped["License"] = relationship(
        "License",
        back_populates="dependency_licenses",
    )

    __table_args__ = (
        UniqueConstraint("dependency_id", "license_id", name="uq_dep_license"),
    )

    def __repr__(self) -> str:
        return f"<DependencyLicense dep={self.dependency_id} lic={self.license_id}>"


class DependencyVersion(Base, PrimaryKeyMixin):
    """Dependency version freshness and upgrade recommendation intelligence."""

    __tablename__ = "dependency_versions"

    dependency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dependencies.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    current_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    latest_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    recommended_version: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    version_status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, name="version_status_enum", native_enum=False),
        default=VersionStatus.UNKNOWN,
        nullable=False,
    )
    release_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    version_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    dependency: Mapped["Dependency"] = relationship(
        "Dependency",
        back_populates="version_info",
    )

    def __repr__(self) -> str:
        return f"<DependencyVersion dep={self.dependency_id} status={self.version_status}>"
