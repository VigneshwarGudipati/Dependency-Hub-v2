import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict
from app.models.scan import ScanType, ScanStatus


class ScanCreate(BaseModel):
    artifact_id: uuid.UUID
    scan_type: ScanType = ScanType.FULL
    configuration: Dict[str, Any] = {}


class ScanResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    artifact_id: uuid.UUID
    status: ScanStatus
    scan_type: ScanType
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Summary metrics
    total_dependencies: int = 0
    vulnerable_dependencies: int = 0
    
    model_config = ConfigDict(from_attributes=True)
