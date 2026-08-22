"""Pydantic schemas for Members (Users scoped to an Organization)."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.models.organization import MemberStatus


class MemberResponse(BaseModel):
    """Frontend representation of a team member."""
    id: uuid.UUID
    name: str
    email: str
    role: str
    status: MemberStatus
    team: str
    lastActive: datetime
    avatarColor: str

    model_config = ConfigDict(from_attributes=True)
