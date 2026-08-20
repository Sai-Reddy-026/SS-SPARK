"""
api/chat.py
Chat conversation and history endpoints for SS SPARK.

Endpoints:
  POST /api/chat           — Submit a question; returns streaming SSE or JSON.
  GET  /api/history        — Fetch past chat messages for a session.

Streaming mode (default):
  The client sends ?stream=true (or omits — default is streaming).
  The server responds with Content-Type: text/event-stream.
  Each SSE event is a JSON payload:
    {"type": "session",  "session_id": "..."}        — sent first, locks in session
    {"type": "phase",    "phase": "routing|retrieving|generating"}
    {"type": "token",    "content": "..."}            — LLM token
    {"type": "meta",     "citations": [...], ...}     — final metadata
    {"type": "done"}                                  — stream complete
    {"type": "error",    "content": "..."}            — on failure

Non-streaming mode (?stream=false):
  Legacy JSON response — identical to the old behaviour.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.security import get_optional_user
from database.models import get_history
from database.user_models import UserRecord
from services.chat_service import ask_question, ask_question_stream

logger = logging.getLogger("ss_spark.chat_api")
router = APIRouter(tags=["Chat"])


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


@router.post("/api/chat")
async def chat_endpoint(
    req: ChatRequest,
    stream: bool = Query(default=True, description="Stream tokens via SSE (default true)"),
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """
    Submit a question for AI answering.
    Automatically routes between PaperQA RAG and general conversational AI.

    Set ?stream=false to receive a legacy JSON response (no streaming).
    """
    if not req.question or not req.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    user_id = current_user.id if current_user else None

    if stream:
        # ── Streaming path ────────────────────────────────────────────────
        async def event_generator():
            try:
                async for chunk in ask_question_stream(
                    question=req.question.strip(),
                    session_id=req.session_id,
                    user_id=user_id,
                ):
                    yield chunk
            except asyncio.CancelledError:
                logger.info("SSE stream cancelled by client")
                raise
            except Exception as exc:
                import json
                logger.exception("Unexpected SSE stream error: %s", exc)
                yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
                "Connection": "keep-alive",
            },
        )

    # ── Non-streaming (legacy JSON) path ──────────────────────────────────
    result = await ask_question(
        question=req.question.strip(),
        session_id=req.session_id,
        user_id=user_id,
    )
    return result


@router.get("/api/history")
async def history_endpoint(
    session_id: str = Query(..., description="Chat session ID"),
    limit: int = Query(50, ge=1, le=200, description="Max messages to return"),
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Fetch past chat messages for a session."""
    user_id = current_user.id if current_user else None
    messages = await get_history(session_id=session_id, limit=limit, user_id=user_id)

    formatted = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at,
            "confidence": m.confidence,
            "citations": [
                {
                    "id": c.id,
                    "source": c.source,
                    "page": c.page,
                    "snippet": c.snippet,
                    "relevance": c.relevance,
                }
                for c in m.citations
            ],
        }
        for m in messages
    ]

    return {
        "success": True,
        "data": formatted,
    }
