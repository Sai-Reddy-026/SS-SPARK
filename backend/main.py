"""
main.py

FastAPI application entry point for the AI Question Paper Analyzer backend.

Start with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Swagger UI available at: http://localhost:8000/docs
ReDoc available at:      http://localhost:8000/redoc
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ss_spark")


# --------------------------------------------------------------------------- #
# Lifespan: startup / shutdown
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown logic."""
    import sys
    from pathlib import Path
    from core.config import get_settings
    from database.models import init_db, get_documents
    from rag import paperqa_connector as pqa

    cfg = get_settings()

    # HIGH-1: Validate JWT secret strength at startup
    _DEFAULT_SECRET = "changeme-please-use-a-long-random-secret-in-production"
    if len(cfg.JWT_SECRET_KEY) < 32 or cfg.JWT_SECRET_KEY == _DEFAULT_SECRET:
        logger.critical(
            "SECURITY: JWT_SECRET_KEY is too weak or is still the default placeholder! "
            "Set a strong random secret (≥32 chars) in backend/.env before going to production."
        )

    logger.info("=" * 60)
    logger.info("  SS Spark Backend — AI Question Paper Analyzer")
    logger.info("  RAG Engine: Existing PaperQA project")
    logger.info("  Swagger UI: http://localhost:%d/docs", cfg.PORT)
    logger.info("=" * 60)


    # ---- MongoDB ----
    await init_db(cfg.MONGO_URI, cfg.MONGO_DB_NAME)

    # ---- Load saved API keys from MongoDB into env ----
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

    # ---- Non-blocking background startup document sync ----
    async def _async_startup_sync():
        try:
            existing_docs = await get_documents(all_users=True)
            if existing_docs:
                logger.info("Re-indexing %d existing documents into PaperQA in background...", len(existing_docs))
                startup_sem = asyncio.Semaphore(4)

                async def _reindex_single_doc(d):
                    if d.file_path and Path(d.file_path).exists():
                        async with startup_sem:
                            await pqa.add_document(d.file_path, user_id=d.user_id)

                await asyncio.gather(*[_reindex_single_doc(d) for d in existing_docs])
                logger.info("PaperQA background startup re-indexing complete.")

            if cfg.USE_QDRANT and existing_docs:
                try:
                    from rag.vector_store import get_vector_store
                    from rag.embeddings import get_embedder
                    from services.pdf_service import extract_chunks
                    from services.image_service import process_image_to_chunks
                    from pathlib import Path as _Path

                    vs = get_vector_store(str(cfg.CHROMA_DIR), cfg.CHROMA_COLLECTION)
                    qdrant_count = vs.count()

                    if qdrant_count == 0:
                        logger.warning("Qdrant collection empty. Rebuilding in background from %d docs...", len(existing_docs))
                        try:
                            embedder = get_embedder()
                        except Exception as emb_err:
                            logger.warning("Qdrant re-index skipped — embedder unavailable: %s", emb_err)
                            embedder = None

                        if embedder:
                            total_reindexed = 0
                            for doc in existing_docs:
                                file_path = doc.file_path
                                if not file_path or not _Path(file_path).exists():
                                    continue
                                try:
                                    suffix = _Path(file_path).suffix.lower()
                                    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                                        sidecar = _Path(file_path).parent / (_Path(file_path).stem + "_ocr.txt")
                                        if not sidecar.exists():
                                            continue
                                        _, chunks = process_image_to_chunks(
                                            file_path, doc.id, str(cfg.UPLOAD_DIR), cfg.CHUNK_SIZE, cfg.CHUNK_OVERLAP
                                        )
                                    else:
                                        chunks = extract_chunks(file_path, doc.id, cfg.CHUNK_SIZE, cfg.CHUNK_OVERLAP)

                                    if not chunks:
                                        continue

                                    texts = [c.text for c in chunks]
                                    pages = [c.page for c in chunks]
                                    embeddings = await asyncio.to_thread(embedder.embed, texts)
                                    vs.add_chunks(
                                        doc_id=doc.id,
                                        source_name=doc.name,
                                        chunks=texts,
                                        embeddings=embeddings,
                                        pages=pages,
                                        user_id=doc.user_id,
                                    )
                                    total_reindexed += len(chunks)
                                except Exception as doc_err:
                                    logger.warning("Qdrant re-index failed for '%s': %s", doc.name, doc_err)

                            logger.info("Qdrant background re-index complete: %d chunks across %d docs.", total_reindexed, len(existing_docs))
                except Exception as qdrant_startup_err:
                    logger.warning("Qdrant startup check failed: %s", qdrant_startup_err)
        except Exception as sync_err:
            logger.warning("Background startup sync error: %s", sync_err)

    asyncio.create_task(_async_startup_sync())

    logger.info("Backend ready ✓  —  FastAPI running, background sync active")
    yield

    # Shutdown
    logger.info("Shutting down SS SPARK backend.")


# --------------------------------------------------------------------------- #
# FastAPI app
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="SS SPARK — AI Question Paper Analyzer API",
    description=(
        "REST API backend powering SS SPARK — AI Question Paper Analyzer. "
        "Upload question papers, notes, and textbooks, then ask questions and get "
        "AI-generated answers grounded in your documents with citations."
    ),
    version="1.0.0",
    contact={"name": "SS SPARK", "url": "https://github.com"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
)


# --------------------------------------------------------------------------- #
# CORS
# --------------------------------------------------------------------------- #

from core.config import get_settings as _get_settings
from core.security import get_cors_origins

_cfg = _get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(_cfg),
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LOW-7: GZip compression — compresses responses >1KB automatically
app.add_middleware(GZipMiddleware, minimum_size=1024)


# LOW-3: Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Adds standard security headers to all HTTP responses:
    - X-Content-Type-Options: prevents MIME-sniffing attacks
    - X-Frame-Options: prevents clickjacking
    - Referrer-Policy: limits referrer information leakage
    - Permissions-Policy: disables unneeded browser features
    """
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# --------------------------------------------------------------------------- #
# Routers
# --------------------------------------------------------------------------- #

from api.upload import router as upload_router
from api.chat import router as chat_router
from api.documents import router as documents_router
from api.users import router as users_router
from api.auth import router as auth_router
from api.sessions import router as sessions_router
from api.analytics import router as analytics_router
from api.admin import router as admin_router
from api.notifications import router as notifications_router

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(users_router)
app.include_router(sessions_router)
app.include_router(analytics_router)
app.include_router(admin_router)
app.include_router(notifications_router)


# --------------------------------------------------------------------------- #
# Static file serving for uploads (optional — enable if needed)
# --------------------------------------------------------------------------- #

_cfg.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_cfg.UPLOAD_DIR)), name="uploads")


# --------------------------------------------------------------------------- #
# Health check
# --------------------------------------------------------------------------- #

@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health():
    """Quick health-check endpoint."""
    from rag import paperqa_connector as pqa
    from database.models import get_documents

    docs = await get_documents()
    return {
        "status": "ok",
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


# --------------------------------------------------------------------------- #
# Global exception handler
# --------------------------------------------------------------------------- #

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An internal server error occurred.",
            "detail": str(exc),
        },
    )


# --------------------------------------------------------------------------- #
# Dev runner
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=_cfg.HOST,
        port=_cfg.PORT,
        reload=True,
        log_level="info",
    )
