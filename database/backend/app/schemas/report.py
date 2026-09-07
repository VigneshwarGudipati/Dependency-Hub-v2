import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from app.models.report import ReportType, ReportFormat, ReportStatus


class ReportCreate(BaseModel):
    scan_id: uuid.UUID
    report_type: ReportType = ReportType.SECURITY_REPORT
    format: ReportFormat = ReportFormat.JSON


class ReportResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    scan_id: Optional[uuid.UUID] = None
    report_type: ReportType
    status: ReportStatus
    created_at: datetime
    created_by: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class ReportDetailResponse(ReportResponse):
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
