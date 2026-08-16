"""
schemas/chat.py
Pydantic validation and serialization schemas for Chat and Citations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class CitationItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    page: int = 1
    snippet: str = ""
    relevance: float = 0.0


# Backward compatibility alias
Citation = CitationItem


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str  # "user" | "assistant"
    content: str
    user_id: Optional[str] = None
    confidence: Optional[float] = None
    citations: List[CitationItem] = Field(default_factory=list)
    references: str = ""
    status: str = "success"  # "success" | "partial" | "unsure" | "general" | "error"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def _coerce_created_at(cls, v: Any) -> str:
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v is not None else ""


class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str = "New Chat"
    pinned: bool = False
    archived: bool = False
    folder: Optional[str] = None
    message_count: int = 0
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _coerce_dates(cls, v: Any) -> str:
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v is not None else ""


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    doc_id: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    source: str = ""
    page: int = 1
    confidence: float = 0.0
    citations: List[CitationItem] = Field(default_factory=list)
    references: str = ""
    session_id: str = ""
    cost: float = 0.0
    status: str = "success"
