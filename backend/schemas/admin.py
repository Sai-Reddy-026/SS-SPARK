"""
schemas/admin.py
Pydantic schemas for SystemSettings and Admin Telemetry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SystemSettings(BaseModel):
    id: str = "global_settings"
    ocr_engine: str = "tesseract"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "gemini-2.0-flash"
    chunk_size: int = 500
    chunk_overlap: int = 50
    max_upload_size_mb: int = 50
    allowed_file_types: List[str] = Field(
        default_factory=lambda: [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp"]
    )
    rate_limit_requests_per_minute: int = 60
    maintenance_mode: bool = False
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AdminStats(BaseModel):
    total_users: int = 0
    total_documents: int = 0
    total_storage_mb: float = 0.0
    total_queries: int = 0
    total_tokens_used: int = 0
    average_latency_ms: float = 0.0
    system_status: str = "operational"
    vector_store_type: str = "ChromaDB"
    rag_engine: str = "PaperQA"
