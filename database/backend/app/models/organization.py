"""Organization and OrganizationMember models representing tenant boundaries."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, SoftDeleteMixin, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.role import Role
    from app.models.project import Project
    from app.models.finding import Finding
    from app.models.policy import SecurityPolicy
    from app.models.audit import AuditLog
    from app.models.report import Report


class MemberStatus(str, enum.Enum):
    """Status of organization membership."""
    ACTIVE = "ACTIVE"
    INVITED = "INVITED"
    SUSPENDED = "SUSPENDED"


class Organization(Base, PrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Organization entity representing the primary tenant boundary."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    members: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    projects: Mapped[List["Project"]] = relationship(
        "Project",
        back_populates="organization",
    )
    findings: Mapped[List["Finding"]] = relationship(
        "Finding",
        back_populates="organization",
    )
    policies: Mapped[List["SecurityPolicy"]] = relationship(
        "SecurityPolicy",
        back_populates="organization",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="organization",
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        back_populates="organization",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name} ({self.slug})>"


class OrganizationMember(Base, PrimaryKeyMixin, TimestampMixin):
    """Join entity between User, Organization, and Role."""

    __tablename__ = "organization_members"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, name="member_status_enum", native_enum=False),
        default=MemberStatus.ACTIVE,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="members",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="memberships",
    )
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="members",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    def __repr__(self) -> str:
        return f"<OrganizationMember org={self.organization_id} user={self.user_id} role={self.role_id}>"
