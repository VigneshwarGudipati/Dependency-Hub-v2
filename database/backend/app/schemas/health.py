from pydantic import BaseModel
from typing import Dict, Any, Optional

class HealthResponse(BaseModel):
    status: str

class DatabaseHealthResponse(BaseModel):
    status: str
    connected: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    postgres_version: Optional[str] = None

class ReadinessResponse(BaseModel):
    status: str
    database: str

class ApiVersionResponse(BaseModel):
    name: str
    version: str

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Dict[str, Any]

class ErrorResponse(BaseModel):
    error: ErrorDetail
