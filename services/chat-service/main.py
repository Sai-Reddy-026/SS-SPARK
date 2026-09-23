"""
services/chat-service/main.py

Chat Service — SS SPARK Microservices
Handles: Chat (RAG + LLM), Sessions, Analytics, Admin panel

Endpoints:
  POST /api/chat         — Submit question (SSE streaming or JSON)
  GET  /api/history      — Fetch chat history
  /api/sessions/*        — Session CRUD
  /api/analytics/*       — User and global analytics
  /api/admin/*           — Admin control panel (users, documents, system health, settings)

Start:
  uvicorn main:app --host 0.0.0.0 --port 8003
"""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# ── Logging ────────────────────────────────────────────────────────────────── #
logger = logging.getLogger("ss_spark.chat_service_app")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# ── Lifespan ───────────────────────────────────────────────────────────────── #
@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.config import get_settings
    from database.models import init_db, get_documents
    from rag import paperqa_connector as pqa

    cfg = get_settings()

    _DEFAULT_SECRET = "changeme-please-use-a-long-random-secret-in-production"
    if len(cfg.JWT_SECRET_KEY) < 32 or cfg.JWT_SECRET_KEY == _DEFAULT_SECRET:
        logger.critical("SECURITY: JWT_SECRET_KEY is too weak or still the default placeholder!")

    logger.info("=" * 60)
    logger.info("  SS Spark — Chat Service")
    logger.info("  RAG Engine: PaperQA")
    logger.info("  Swagger UI: http://localhost:8003/docs")
    logger.info("=" * 60)

    # ── MongoDB ── #
    await init_db(cfg.MONGO_URI, cfg.MONGO_DB_NAME)

    # ── Load saved API keys ── #
    try:
        from database.models import load_settings
        saved_settings = await load_settings()
        if saved_settings:
            from core.security import update_api_keys
            update_api_keys(
                saved_settings.openai_api_key,
                saved_settings.gemini_api_key,
                saved_settings.anthropic_api_key,
            )
            logger.info("Loaded API keys from database.")
    except Exception as exc:
        logger.warning("Could not load saved settings: %s", exc)

    logger.info("Chat Service ready ✓")
    yield
    logger.info("Shutting down Chat Service.")


# ── App ────────────────────────────────────────────────────────────────────── #
app = FastAPI(
    title="SS SPARK — Chat Service",
    description=(
        "Chat, session management, analytics, and admin microservice for SS SPARK. "
        "Handles RAG-grounded Q&A with multi-phase SSE streaming, session CRUD, "
        "usage analytics, and the admin control panel."
    ),
    version="1.0.0",
    contact={"name": "SS SPARK"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────── #
from core.config import get_settings as _gs
from core.security import get_cors_origins

_cfg = _gs()
_cors_origins = get_cors_origins(_cfg)
_has_wildcard = "*" in _cors_origins or "*" in _cfg.ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if not _has_wildcard else ["*"],
    allow_origin_regex=(
        r".*"
        if _has_wildcard
        else (
            r"^https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?$"
            r"|^https:\/\/(?:[a-zA-Z0-9_\-]+\.)*(?:ss-spark|ssspark)(?:-[a-zA-Z0-9_\-]+)?"
            r"\.(?:vercel\.app|onrender\.com|pages\.dev|netlify\.app|lovableproject\.com|lovable\.app)$"
        )
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


# ── Security headers ───────────────────────────────────────────────────────── #
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# ── Routers ────────────────────────────────────────────────────────────────── #
from api.chat import router as chat_router
from api.sessions import router as sessions_router
from api.analytics import router as analytics_router
from api.admin import router as admin_router

app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(analytics_router)
app.include_router(admin_router)


# ── Health ─────────────────────────────────────────────────────────────────── #
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health():
    """Chat Service health check (also serves as the primary system health endpoint via gateway)."""
    from rag import paperqa_connector as pqa
    from database.models import get_documents, get_db
    from rag.vector_store import get_vector_store
    from core.config import get_settings

    cfg = get_settings()
    docs = await get_documents()
    db = get_db()

    vector_status = "in-memory"
    try:
        vs = get_vector_store()
        if vs.qdrant_client is not None:
            vector_status = "qdrant"
        elif vs.chroma_collection is not None:
            vector_status = "chromadb"
    except Exception:
        pass

    return {
        "status": "ok",
        "service": "chat-service",
        "gemini": "configured" if cfg.has_gemini else "missing",
        "nvidia": "configured" if cfg.has_nvidia else "missing",
        "primary_provider": cfg.primary_llm_provider,
        "fallback_provider": cfg.fallback_llm_provider,
        "mongodb": "connected" if db is not None else "in-memory-fallback",
        "vector_store": vector_status,
        "documents_in_db": len(docs),
        "paperqa_indexed": pqa.get_indexed_count(),
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "SS SPARK API is running.",
        "docs": "/docs",
        "health": "/health",
    }


# ── Global exception handler ───────────────────────────────────────────────── #
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "An internal server error occurred.", "detail": str(exc)},
    )


# ── Dev runner ─────────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True, log_level="info")
