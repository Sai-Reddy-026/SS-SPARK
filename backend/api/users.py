"""
api/users.py
User profile management endpoints for SS SPARK.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.security import get_current_user
from database.user_models import UserRecord, update_user

router = APIRouter(prefix="/api/users", tags=["Users"])


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


@router.get("/me")
async def get_me(current_user: UserRecord = Depends(get_current_user)):
    """Fetch current authenticated user profile."""
    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "avatar_url": current_user.avatar_url,
            "role": current_user.role,
            "status": current_user.status,
            "email_verified": current_user.email_verified,
            "provider": current_user.provider,
            "created_at": current_user.created_at,
        },
    }


@router.patch("/me")
async def update_me(
    req: UserUpdateRequest,
    current_user: UserRecord = Depends(get_current_user),
):
    """Update profile fields."""
    updates = req.model_dump(exclude_unset=True)
    if updates:
        await update_user(current_user.id, updates)
    return {
        "success": True,
        "message": "Profile updated successfully.",
    }
