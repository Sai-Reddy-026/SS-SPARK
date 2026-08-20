"""
api/sessions.py
Chat session management endpoints for SS SPARK.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.security import get_optional_user
from database.models import ChatSession, create_session, delete_session, get_session_by_id, get_sessions, update_session
from database.user_models import UserRecord

logger = logging.getLogger("ss_spark.sessions_api")
router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


class CreateSessionRequest(BaseModel):
    title: str = "New Chat"


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None
    folder: Optional[str] = None


@router.get("")
async def list_sessions(current_user: Optional[UserRecord] = Depends(get_optional_user)):
    """List chat sessions for the active user."""
    user_id = current_user.id if current_user else "anonymous"
    sessions = await get_sessions(user_id=user_id)
    return {
        "success": True,
        "data": [s.model_dump() for s in sessions],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def new_session(
    req: CreateSessionRequest,
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Create a new chat session."""
    user_id = current_user.id if current_user else "anonymous"
    session = ChatSession(
        user_id=user_id,
        title=req.title or "New Chat",
    )
    created = await create_session(session)
    return {
        "success": True,
        "data": created.model_dump(),
    }


from core.security import get_current_user, get_optional_user

@router.patch("/{session_id}")
async def modify_session(
    session_id: str,
    req: UpdateSessionRequest,
    current_user: UserRecord = Depends(get_current_user),
):
    """Update title, pinned, or archived status of a session."""
    updates = req.model_dump(exclude_unset=True)
    updated = await update_session(session_id, updates, user_id=current_user.id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    return {
        "success": True,
        "data": updated.model_dump(),
    }


@router.delete("/{session_id}")
async def remove_session(
    session_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    """
    Delete a chat session and all messages within it.
    SEC-02 FIX: Requires authenticated user and verifies strict user_id ownership.
    """
    deleted = await delete_session(session_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    return {
        "success": True,
        "message": "Session deleted successfully.",
    }
