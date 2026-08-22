from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict


class ArtifactBase(BaseModel):
    version_number: int
    source_type: str
    original_filename: str
    size_bytes: int
    content_hash: str
    upload_status: str


class ArtifactCreate(ArtifactBase):
    project_id: uuid.UUID
    storage_provider: str = "local"
    storage_bucket: Optional[str] = None
    storage_key: str
    encrypted_storage_key: Optional[str] = None
    file_count: int = 1
    uploaded_by: Optional[uuid.UUID] = None


class ArtifactResponse(ArtifactBase):
    id: uuid.UUID
    project_id: uuid.UUID
    is_immutable: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
