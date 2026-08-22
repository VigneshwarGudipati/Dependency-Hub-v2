"""Tests for immutable artifact lifecycle, envelope encryption metadata, and workspaces."""

import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    AnalysisWorkspace,
    ArtifactEncryptionMetadata,
    ArtifactSourceType,
    ArtifactUploadStatus,
    Project,
    ProjectArtifact,
    Scan,
    User,
    WorkspaceStatus,
)


@pytest.mark.asyncio
async def test_artifact_version_increment_and_uniqueness(
    seeded_session: AsyncSession,
    sample_project: Project,
    sample_user: User,
):
    """Verify that artifact versions increment monotonically and duplicate versions are rejected."""
    # Version 1
    artifact_v1 = ProjectArtifact(
        project_id=sample_project.id,
        version_number=1,
        source_type=ArtifactSourceType.UPLOAD,
        original_filename="service-v1.0.0.zip",
        storage_key="s3://bucket/artifacts/v1.zip",
        content_hash="hash_v1_sha256",
        is_immutable=True,
    )
    seeded_session.add(artifact_v1)
    await seeded_session.flush()

    # Version 2
    artifact_v2 = ProjectArtifact(
        project_id=sample_project.id,
        version_number=2,
        source_type=ArtifactSourceType.UPLOAD,
        original_filename="service-v1.1.0.zip",
        storage_key="s3://bucket/artifacts/v2.zip",
        content_hash="hash_v2_sha256",
        is_immutable=True,
    )
    seeded_session.add(artifact_v2)
    await seeded_session.flush()

    assert artifact_v1.id != artifact_v2.id
    assert artifact_v2.version_number == 2

    # Attempt duplicate Version 1 for same project
    dup_v1 = ProjectArtifact(
        project_id=sample_project.id,
        version_number=1,
        original_filename="attempted-overwrite.zip",
        storage_key="s3://bucket/artifacts/v1_overwrite.zip",
        content_hash="hash_v1_new",
    )
    seeded_session.add(dup_v1)
    with pytest.raises(IntegrityError):
        await seeded_session.flush()


@pytest.mark.asyncio
async def test_envelope_encryption_metadata_one_to_one(
    seeded_session: AsyncSession,
    sample_project: Project,
):
    """Verify 1-to-1 envelope encryption relationship and unique constraint."""
    artifact = ProjectArtifact(
        project_id=sample_project.id,
        version_number=1,
        original_filename="code.zip",
        storage_key="k1",
        content_hash="h1",
    )
    seeded_session.add(artifact)
    await seeded_session.flush()

    enc_1 = ArtifactEncryptionMetadata(
        artifact_id=artifact.id,
        algorithm="AES-256-GCM",
        encryption_version="v1",
        key_reference="vault/keys/app-kek",
        initialization_vector="iv123",
        authentication_tag="tag123",
        encrypted_dek_reference="enc_dek_123",
        checksum="chk123",
    )
    seeded_session.add(enc_1)
    await seeded_session.flush()

    # Attempt second encryption metadata for same artifact
    enc_2 = ArtifactEncryptionMetadata(
        artifact_id=artifact.id,
        algorithm="AES-256-GCM",
        encryption_version="v1",
        key_reference="vault/keys/app-kek",
        initialization_vector="iv456",
        authentication_tag="tag456",
        encrypted_dek_reference="enc_dek_456",
        checksum="chk456",
    )
    seeded_session.add(enc_2)
    with pytest.raises(IntegrityError):
        await seeded_session.flush()


@pytest.mark.asyncio
async def test_workspace_isolation_and_lifecycle(
    seeded_session: AsyncSession,
    sample_project: Project,
):
    """Verify analysis workspaces are ephemeral and maintain reference to the immutable artifact."""
    artifact = ProjectArtifact(
        project_id=sample_project.id,
        version_number=1,
        original_filename="repo.zip",
        storage_key="k1",
        content_hash="h1",
    )
    seeded_session.add(artifact)
    await seeded_session.flush()

    workspace = AnalysisWorkspace(
        artifact_id=artifact.id,
        workspace_identifier=f"ws-{uuid.uuid4().hex}",
        storage_reference="/sandboxes/ws-test",
        status=WorkspaceStatus.ANALYZING,
    )
    seeded_session.add(workspace)
    await seeded_session.flush()

    assert workspace.status == WorkspaceStatus.ANALYZING
    assert workspace.artifact_id == artifact.id
