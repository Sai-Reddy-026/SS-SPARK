"""
services/document-service/main.py

Document Service — SS SPARK Microservices
Handles: Document upload, RAG indexing, vector store, document management

Endpoints:
  POST /api/upload       — Upload documents, extract text, embed and index
  GET  /api/documents    — List user documents
  DELETE /api/documents/{id} — Delete document + vectors + file
  PATCH  /api/documents/{id} — Rename document

Start:
  uvicorn main:app --host 0.0.0.0 --port 8002
"""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Logging ────────────────────────────────────────────────────────────────── #
logger = logging.getLogger("ss_spark.document_service")
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

    logger.info("=" * 60)
    logger.info("  SS Spark — Document Service")
    logger.info("  Swagger UI: http://localhost:8002/docs")
    logger.info("=" * 60)

    # ── MongoDB ── #
    await init_db(cfg.MONGO_URI, cfg.MONGO_DB_NAME)

    # ── Background startup document re-index ── #
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
                        logger.warning("Qdrant collection empty. Rebuilding from %d docs...", len(existing_docs))
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
                                        _, chunks, _ = process_image_to_chunks(
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
                            logger.info("Qdrant re-index complete: %d chunks.", total_reindexed)
                except Exception as qdrant_err:
                    logger.warning("Qdrant startup check failed: %s", qdrant_err)
        except Exception as sync_err:
            logger.warning("Background startup sync error: %s", sync_err)

    asyncio.create_task(_async_startup_sync())
    logger.info("Document Service ready ✓  — background sync active")
    yield
    logger.info("Shutting down Document Service.")


# ── App ────────────────────────────────────────────────────────────────────── #
app = FastAPI(
    title="SS SPARK — Document Service",
    description=(
        "Document upload, text extraction, vector embedding, and RAG indexing microservice. "
        "Supports PDF, DOCX, TXT, images (OCR), PPTX, BIB."
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
from api.upload import router as upload_router
from api.documents import router as documents_router

app.include_router(upload_router)
app.include_router(documents_router)

# ── Static files (uploaded documents) ─────────────────────────────────────── #
_cfg.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_cfg.UPLOAD_DIR)), name="uploads")


# ── Health ─────────────────────────────────────────────────────────────────── #
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health():
    """Document Service health check."""
    from rag import paperqa_connector as pqa
    from rag.vector_store import get_vector_store
    from database.models import get_documents, get_db

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
        "service": "document-service",
        "mongodb": "connected" if db is not None else "in-memory-fallback",
        "vector_store": vector_status,
        "documents_in_db": len(docs),
        "paperqa_indexed": pqa.get_indexed_count(),
    }


@app.get("/", tags=["Root"])
async def root():
    return {"message": "SS SPARK Document Service is running.", "docs": "/docs"}


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
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True, log_level="info")
