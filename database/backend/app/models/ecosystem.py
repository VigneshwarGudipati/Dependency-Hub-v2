"""Package Ecosystem model for normalized package registry classifications."""

from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.dependency import Dependency


class PackageEcosystem(Base, PrimaryKeyMixin, TimestampMixin):
    """Normalized package ecosystem entity (e.g., npm, PyPI, Maven, Cargo, Go)."""

    __tablename__ = "package_ecosystems"

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    default_package_manager: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Relationships
    dependencies: Mapped[List["Dependency"]] = relationship(
        "Dependency",
        back_populates="ecosystem",
    )

    def __repr__(self) -> str:
        return f"<PackageEcosystem {self.name}>"
