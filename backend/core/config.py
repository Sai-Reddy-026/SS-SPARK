"""
core/config.py
Application-wide configuration loaded from environment variables.
Uses pydantic-settings for validation and type coercion.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All environment-variable-backed settings for the backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PaperQA Project Directory
    PAPERQA_PROJECT_DIR: str = Field(
        default="",
        description="Path to local PaperQA project src directory (optional override)",
    )


    # ------------------------------------------------------------------ #
    # LLM / Embedding API keys
    # ------------------------------------------------------------------ #
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key")
    # MED-8: GOOGLE_API_KEY is the alias LiteLLM uses for Gemini — keep in sync with GEMINI_API_KEY
    GOOGLE_API_KEY: str = Field(default="", description="Google API key (alias for GEMINI_API_KEY, used by LiteLLM)")
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic Claude API key")
    NVIDIA_API_KEY: str = Field(default="", description="NVIDIA NIM API key")
    NVIDIA_NIM_API_KEY: str = Field(default="", description="NVIDIA NIM API key (alias)")

    # ------------------------------------------------------------------ #
    # JWT Authentication
    # ------------------------------------------------------------------ #
    JWT_SECRET_KEY: str = Field(
        default="changeme-please-use-a-long-random-secret-in-production",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "JWT_SECRET"),
        description="Secret key for signing JWT tokens. MUST be overridden in production.",
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="Access token TTL in minutes")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, description="Refresh token TTL in days")

    # ------------------------------------------------------------------ #
    # OAuth (Google + GitHub)
    # ------------------------------------------------------------------ #
    GOOGLE_CLIENT_ID: str = Field(default="", description="Google OAuth 2.0 client ID")
    GOOGLE_CLIENT_SECRET: str = Field(default="", description="Google OAuth 2.0 client secret")
    GITHUB_CLIENT_ID: str = Field(default="", description="GitHub OAuth app client ID")
    GITHUB_CLIENT_SECRET: str = Field(default="", description="GitHub OAuth app client secret")

    # ------------------------------------------------------------------ #
    # Email / SMTP / Resend (for verification & password reset)
    # ------------------------------------------------------------------ #
    EMAIL_PROVIDER: str = Field(default="", description="Email provider: 'resend', 'smtp', or 'log'")
    EMAIL_FROM: str = Field(default="noreply@ssspark.ai", description="From address for emails")
    RESEND_API_KEY: str = Field(default="", description="Resend.com API key (if using Resend)")
    SMTP_HOST: str = Field(default="", description="SMTP server hostname")
    SMTP_PORT: int = Field(default=587, description="SMTP port")
    SMTP_USER: str = Field(default="", description="SMTP username")
    SMTP_PASS: str = Field(default="", description="SMTP password")
    SMTP_FROM: str = Field(default="noreply@ssspark.ai", description="Legacy alias for EMAIL_FROM")

    # ------------------------------------------------------------------ #
    # Frontend URL (used in email links)
    # ------------------------------------------------------------------ #
    FRONTEND_URL: str = Field(
        default="http://localhost:8080",
        description="Public frontend URL for building email links and OAuth redirects",
    )

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    MONGO_URI: str = Field(
        default="mongodb://localhost:27017",
        validation_alias=AliasChoices("MONGO_URI", "MONGODB_URI"),
        description="MongoDB connection URI",
    )
    MONGO_DB_NAME: str = Field(default="ss_spark", description="MongoDB database name")

    # ------------------------------------------------------------------ #
    # File storage
    # ------------------------------------------------------------------ #
    UPLOAD_DIR: Path = Field(
        default=Path(__file__).parent.parent / "uploads",
        description="Directory where uploaded files are stored",
    )
    MAX_FILE_SIZE_MB: int = Field(default=50, description="Maximum allowed upload size in MB")
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".bib", ".pptx"],
        description="Whitelisted file extensions",
    )

    # ------------------------------------------------------------------ #
    # Vector store
    # ------------------------------------------------------------------ #
    CHROMA_DIR: Path = Field(
        default=Path(__file__).parent.parent / "chroma_db",
        description="ChromaDB persistent storage directory",
    )
    CHROMA_COLLECTION: str = Field(
        default="ss_spark_chunks",
        description="ChromaDB collection name",
    )

    # ------------------------------------------------------------------ #
    # Qdrant vector database
    # ------------------------------------------------------------------ #
    USE_QDRANT: bool = Field(
        default=True,
        description="Use Qdrant as the primary vector store (set False to fall back to ChromaDB).",
    )
    QDRANT_HOST: str = Field(
        default="localhost",
        description="Qdrant server hostname.",
    )
    QDRANT_PORT: int = Field(
        default=6333,
        description="Qdrant gRPC/REST port.",
    )
    QDRANT_API_KEY: str = Field(
        default="",
        description="Qdrant API key (leave empty for local unauthenticated instances).",
    )
    QDRANT_COLLECTION: str = Field(
        default="ss_spark_chunks",
        description="Qdrant collection name for document chunk vectors.",
    )

    # ------------------------------------------------------------------ #
    # RAG / Chunking
    # ------------------------------------------------------------------ #
    CHUNK_SIZE: int = Field(default=500, description="Target token size for text chunks")
    CHUNK_OVERLAP: int = Field(default=50, description="Token overlap between consecutive chunks")
    TOP_K_RESULTS: int = Field(default=5, description="Number of chunks to retrieve per query")

    # ------------------------------------------------------------------ #
    # Server
    # ------------------------------------------------------------------ #
    ALLOWED_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
        ],
        description="CORS-allowed origins",
    )
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @property
    def has_oauth_google(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def has_oauth_github(self) -> bool:
        return bool(self.GITHUB_CLIENT_ID and self.GITHUB_CLIENT_SECRET)

    @property
    def has_smtp(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER)

    @property
    def has_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY)

    @property
    def has_gemini(self) -> bool:
        # MED-8: Either GEMINI_API_KEY or GOOGLE_API_KEY counts as Gemini configured
        return bool(self.GEMINI_API_KEY or self.GOOGLE_API_KEY)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)

    @property
    def has_nvidia(self) -> bool:
        return bool(self.NVIDIA_API_KEY or self.NVIDIA_NIM_API_KEY)

    @property
    def primary_llm_provider(self) -> str:
        """Return the primary provider name based on active keys."""
        if self.has_gemini:
            return "gemini"
        if self.has_nvidia:
            return "nvidia"
        if self.has_openai:
            return "openai"
        if self.has_anthropic:
            return "anthropic"
        return "none"

    @property
    def fallback_llm_provider(self) -> str:
        """Return the fallback provider name based on active keys."""
        if self.has_gemini and self.has_nvidia:
            return "nvidia"
        if (self.has_gemini or self.has_nvidia) and self.has_openai:
            return "openai"
        return "none"

    @property
    def has_any_llm_key(self) -> bool:
        return self.has_openai or self.has_gemini or self.has_anthropic or self.has_nvidia

    def apply_to_env(self) -> None:
        """Push API keys back into os.environ so PaperQA and LiteLLM pick them up."""
        if self.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY
        
        # Sync Gemini keys
        gemini_val = self.GEMINI_API_KEY or self.GOOGLE_API_KEY
        if gemini_val:
            os.environ["GEMINI_API_KEY"] = gemini_val
            os.environ["GOOGLE_API_KEY"] = gemini_val

        if self.ANTHROPIC_API_KEY:
            os.environ["ANTHROPIC_API_KEY"] = self.ANTHROPIC_API_KEY

        # Sync NVIDIA keys
        nvidia_val = self.NVIDIA_API_KEY or self.NVIDIA_NIM_API_KEY
        if nvidia_val:
            os.environ["NVIDIA_API_KEY"] = nvidia_val
            os.environ["NVIDIA_NIM_API_KEY"] = nvidia_val


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    settings = Settings()
    # Ensure directories exist
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    settings.apply_to_env()
    return settings
