"""
api/notifications.py
In-app user notification endpoints for SS SPARK.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from core.security import get_optional_user
from database.user_models import UserRecord, get_notifications, mark_notifications_read

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
async def list_user_notifications(current_user: Optional[UserRecord] = Depends(get_optional_user)):
    """Fetch notifications for current user."""
    user_id = current_user.id if current_user else "anonymous"
    notifications = await get_notifications(user_id=user_id)
    return {
        "success": True,
        "data": [n.model_dump() for n in notifications],
    }


@router.post("/read")
async def mark_read(current_user: Optional[UserRecord] = Depends(get_optional_user)):
    """Mark all notifications as read."""
    user_id = current_user.id if current_user else "anonymous"
    await mark_notifications_read(user_id=user_id)
    return {
        "success": True,
        "message": "Notifications marked as read.",
    }
