"""Artifact encryption metadata model supporting envelope encryption."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.artifact import ProjectArtifact


class ArtifactEncryptionMetadata(Base, PrimaryKeyMixin):
    """Envelope encryption metadata for stored project artifacts.
    
    Security Guarantee:
    PostgreSQL stores ONLY metadata, initialization vectors, authentication tags,
    and encrypted Data Encryption Keys (DEKs). Master keys and Key Encryption Keys
    (KEKs) reside exclusively in external KMS (Vault, AWS KMS, GCP KMS).
    """

    __tablename__ = "artifact_encryption_metadata"

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_artifacts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    algorithm: Mapped[str] = mapped_column(
        String(50),
        default="AES-256-GCM",
        nullable=False,
    )
    encryption_version: Mapped[str] = mapped_column(
        String(20),
        default="v1",
        nullable=False,
    )
    key_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="External KMS Key Identifier / Vault Key Name",
    )
    initialization_vector: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Base64 encoded IV / Nonce",
    )
    authentication_tag: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Base64 encoded GCM authentication tag",
    )
    encrypted_dek_reference: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Base64 encoded encrypted Data Encryption Key",
    )
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 checksum of the ciphertext",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    artifact: Mapped["ProjectArtifact"] = relationship(
        "ProjectArtifact",
        back_populates="encryption_metadata",
    )

    def __repr__(self) -> str:
        return f"<ArtifactEncryptionMetadata artifact_id={self.artifact_id} algo={self.algorithm}>"
