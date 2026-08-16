"""
api/analytics.py
Analytics and dashboard metrics endpoints for SS SPARK.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.security import get_optional_user
from database.models import get_activity_data, get_panel_stats, get_user_stats
from database.user_models import UserRecord

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/user")
@router.get("/stats")
async def user_analytics(current_user: Optional[UserRecord] = Depends(get_optional_user)):
    """User-level metrics and usage counts."""
    user_id = current_user.id if current_user else "anonymous"
    stats = await get_user_stats(user_id=user_id)
    return {
        "success": True,
        "data": stats,
    }


@router.get("/activity")
async def activity_analytics(
    days: int = Query(14, ge=1, le=90),
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Activity frequency per day for trend charts."""
    user_id = current_user.id if current_user else None
    activity = await get_activity_data(user_id=user_id, days=days)
    return {
        "success": True,
        "data": activity,
    }


@router.get("/panel")
async def panel_analytics(current_user: Optional[UserRecord] = Depends(get_optional_user)):
    """Document analyzer side-panel statistics (topic distribution, repeat trends)."""
    user_id = current_user.id if current_user else None
    panel_stats = await get_panel_stats(user_id=user_id)
    return {
        "success": True,
        "data": panel_stats,
    }
