"""Registry Cache model."""

import uuid
from datetime import datetime
from typing import Any, Dict
from sqlalchemy import DateTime, Enum, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PrimaryKeyMixin, TimestampMixin
from app.services.registry.base import RegistryStatus

class RegistryCache(Base, PrimaryKeyMixin, TimestampMixin):
    """Cache for package registry metadata."""

    __tablename__ = "registry_cache"

    ecosystem: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    status: Mapped[RegistryStatus] = mapped_column(
        Enum(RegistryStatus, name="registry_status_enum", native_enum=False),
        nullable=False,
    )

    registry_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=True,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("ecosystem", "package_name", name="uq_registry_cache_ecosystem_package"),
    )

    def __repr__(self) -> str:
        return f"<RegistryCache {self.ecosystem}:{self.package_name} ({self.status.value})>"
