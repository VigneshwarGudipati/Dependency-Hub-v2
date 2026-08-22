"""Pydantic schemas for Projects (Repositories) and their statistics."""

from datetime import datetime
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.project import ProjectVisibility


class ProjectBase(BaseModel):
    """Base project attributes."""
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    language: Optional[str] = Field(None, max_length=100)
    visibility: ProjectVisibility = Field(default=ProjectVisibility.ORGANIZATION)
    branch: str = Field(..., max_length=100)


class ProjectCreate(ProjectBase):
    """Payload for creating a new project/repository."""
    url: Optional[str] = Field(None, max_length=500)


class ProjectResponse(ProjectBase):
    """Frontend representation of a repository with project statistics."""
    id: uuid.UUID
    owner: str  # Can be the organization name or the creator's username
    healthScore: int
    dependencies: int
    vulnerabilities: int
    outdated: int
    lastScan: Optional[datetime]
    createdAt: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)

