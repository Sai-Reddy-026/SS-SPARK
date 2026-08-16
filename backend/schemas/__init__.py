"""
schemas package
Unified Pydantic models for HTTP request payloads, responses, and serialization.
"""

from schemas.chat import ChatMessage, ChatSession, ChatRequest, ChatResponse, CitationItem, Citation
from schemas.document import UploadedDoc, DocumentResponse, DocumentListResponse
from schemas.admin import SystemSettings, AdminStats
from schemas.auth import RegisterRequest, LoginRequest, RefreshTokenRequest, TokenResponse, UserResponse

__all__ = [
    "ChatMessage",
    "ChatSession",
    "ChatRequest",
    "ChatResponse",
    "CitationItem",
    "Citation",
    "UploadedDoc",
    "DocumentResponse",
    "DocumentListResponse",
    "SystemSettings",
    "AdminStats",
    "RegisterRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "TokenResponse",
    "UserResponse",
]
