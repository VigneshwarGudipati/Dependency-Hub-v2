"""Pydantic schemas for authentication request/response contracts."""

import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# --- Requests ---

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Full name")
    company: str = Field("", max_length=255, description="Company/organization name")
    email: EmailStr = Field(..., description="Work email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Work email address")
    password: str = Field(..., min_length=1, max_length=128, description="Password")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Current refresh token")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token to revoke")


# --- Responses ---

class OrganizationInfo(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    full_name: Optional[str] = None
    is_active: bool
    organization: Optional[OrganizationInfo] = None
    role: Optional[str] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str
    user: UserResponse
