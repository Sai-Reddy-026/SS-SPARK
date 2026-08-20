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


class UserApiKeysRequest(BaseModel):
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None


@router.get("/settings")
async def get_user_settings(current_user: UserRecord = Depends(get_current_user)):
    """Return status of configured LLM API keys."""
    from core.config import get_settings
    cfg = get_settings()
    return {
        "success": True,
        "data": {
            "has_openai": cfg.has_openai,
            "has_gemini": cfg.has_gemini,
            "has_anthropic": cfg.has_anthropic,
        },
    }


@router.post("/settings")
async def update_user_settings(
    req: UserApiKeysRequest,
    current_user: UserRecord = Depends(get_current_user),
):
    """
    Save system-wide API keys.
    SEC-01 FIX: Restricted strictly to ADMIN users to prevent multi-tenant key hijacking.
    """
    from database.user_models import UserRole
    if current_user.role != UserRole.ADMIN:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required to configure system-wide API keys.",
        )

    from core.security import update_api_keys
    from database.models import load_settings, save_settings, SystemSettings

    settings = await load_settings() or SystemSettings()
    if req.openai_api_key is not None:
        settings.openai_api_key = req.openai_api_key
    if req.gemini_api_key is not None:
        settings.gemini_api_key = req.gemini_api_key
    if req.anthropic_api_key is not None:
        settings.anthropic_api_key = req.anthropic_api_key

    await save_settings(settings)
    update_api_keys(
        openai_api_key=req.openai_api_key,
        gemini_api_key=req.gemini_api_key,
        anthropic_api_key=req.anthropic_api_key,
    )

    return {
        "success": True,
        "message": "API keys saved successfully.",
    }

