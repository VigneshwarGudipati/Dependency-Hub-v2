import hashlib
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.artifact import ProjectArtifact, ArtifactSourceType, ArtifactUploadStatus
from app.models.project import Project
from app.models.encryption import ArtifactEncryptionMetadata
from app.services.encryption_service import key_provider, encrypt_artifact

# Use a temporary directory for processing
TEMP_DIR = Path(settings.STORAGE_DIR) / "temp"
ENCRYPTED_DIR = Path(settings.STORAGE_DIR) / "encrypted"


async def validate_filename(filename: str) -> None:
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    if "\x00" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Path traversal checks
    p = Path(filename)
    if p.is_absolute() or ".." in p.parts or any(part.startswith("\\\\") for part in p.parts):
        raise HTTPException(status_code=400, detail="Path traversal detected in filename")


async def validate_archive(file_path: Path) -> None:
    if not zipfile.is_zipfile(file_path):
        return  # Not a ZIP, standard file is fine
    
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            total_size = 0
            file_count = 0
            for info in zf.infolist():
                if info.is_dir():
                    continue
                file_count += 1
                total_size += info.file_size
                
                # Check traversal in archive
                p = Path(info.filename)
                if p.is_absolute() or ".." in p.parts:
                    raise HTTPException(status_code=400, detail="Invalid archive: path traversal")
                
                if file_count > 10000:
                    raise HTTPException(status_code=400, detail="Invalid archive: too many files")
                if total_size > settings.MAX_ARTIFACT_SIZE_BYTES * 5:
                    raise HTTPException(status_code=400, detail="Invalid archive: excessive uncompressed size")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid archive: malformed ZIP")


async def create_artifact(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    file: UploadFile,
    filename: str
) -> ProjectArtifact:
    # 1. Authorize project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Validate filename
    await validate_filename(filename)
    
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_file_path = TEMP_DIR / f"{uuid.uuid4()}_{filename}"
    
    # 3. Read, Hash, and Validate Size
    sha256 = hashlib.sha256()
    size_bytes = 0
    plaintext_data = bytearray()
    
    try:
        with open(temp_file_path, "wb") as f:
            while True:
                chunk = await file.read(65536)
                if not chunk:
                    break
                sha256.update(chunk)
                size_bytes += len(chunk)
                plaintext_data.extend(chunk)
                
                if size_bytes > settings.MAX_ARTIFACT_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail="Artifact exceeds maximum allowed size")
                f.write(chunk)
        
        # 4. Validate archive if applicable
        await validate_archive(temp_file_path)
        
        # 5. Generate random DEK and encrypt the payload
        dek, b64_encrypted_dek = key_provider.generate_dek()
        ciphertext, b64_nonce, b64_tag, b64_checksum = encrypt_artifact(bytes(plaintext_data), dek)
        
        # Secure cleanup of plaintext from memory
        plaintext_data.clear()
        
        # 6. Save encrypted file to storage
        project_storage_dir = ENCRYPTED_DIR / str(project_id)
        project_storage_dir.mkdir(parents=True, exist_ok=True)
        
        artifact_id = uuid.uuid4()
        encrypted_storage_key = str(project_storage_dir / str(artifact_id))
        
        with open(encrypted_storage_key, "wb") as ef:
            ef.write(ciphertext)

        # Determine version number
        stmt = select(ProjectArtifact.version_number).where(ProjectArtifact.project_id == project_id).order_by(ProjectArtifact.version_number.desc()).limit(1)
        res = await db.execute(stmt)
        latest_version = res.scalar_one_or_none()
        next_version = (latest_version or 0) + 1
        
        # 7. Save Artifact record
        artifact = ProjectArtifact(
            id=artifact_id,
            project_id=project_id,
            version_number=next_version,
            source_type=ArtifactSourceType.UPLOAD,
            original_filename=filename,
            storage_provider="local",
            storage_bucket="encrypted",
            storage_key=encrypted_storage_key,
            content_hash=sha256.hexdigest(),
            size_bytes=size_bytes,
            upload_status=ArtifactUploadStatus.READY,
            uploaded_by=user_id,
            is_immutable=True
        )
        db.add(artifact)
        
        # 8. Save Encryption Metadata
        enc_meta = ArtifactEncryptionMetadata(
            artifact_id=artifact_id,
            algorithm="AES-256-GCM",
            encryption_version="v1",
            key_reference="local_master_key",
            initialization_vector=b64_nonce,
            authentication_tag=b64_tag,
            encrypted_dek_reference=b64_encrypted_dek,
            checksum=b64_checksum
        )
        db.add(enc_meta)
        
        await db.commit()
        await db.refresh(artifact)
        
        return artifact
    except Exception as e:
        # If writing encrypted failed, clean it up if we know the path
        try:
            if 'encrypted_storage_key' in locals() and os.path.exists(encrypted_storage_key):
                os.remove(encrypted_storage_key)
        except Exception:
            pass
        raise e
    finally:
        # 9. Cleanup temp workspace
        if temp_file_path.exists():
            temp_file_path.unlink()
