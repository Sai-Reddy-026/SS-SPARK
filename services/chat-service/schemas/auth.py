"""
schemas/auth.py
Pydantic schemas for authentication requests, tokens, and user models.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str = "user"
    status: str = "active"
    avatar_url: Optional[str] = None
    created_at: str
