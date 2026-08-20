"""
schemas/document.py
Pydantic validation schemas for document upload and retrieval.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class UploadedDoc(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    kind: str = "pdf"
    size_mb: float = 0.0
    pages: int = 1
    chunk_count: int = 0
    file_path: str = ""
    user_id: Optional[str] = None
    sha256: Optional[str] = None
    uploaded_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @field_validator("uploaded_at", mode="before")
    @classmethod
    def _coerce_uploaded_at(cls, v: Any) -> str:
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v) if v is not None else ""


class DocumentResponse(BaseModel):
    id: str
    name: str
    kind: str
    size_mb: float
    pages: int
    chunk_count: int
    uploaded_at: str


class DocumentListResponse(BaseModel):
    success: bool = True
    documents: List[DocumentResponse] = Field(default_factory=list)
