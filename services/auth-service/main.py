"""
services/auth-service/main.py

Auth Service — SS SPARK Microservices
Handles: Authentication, User Profile, Notifications

Endpoints:
  /api/auth/*          — Registration, login, OAuth, password reset, token refresh
  /api/users/*         — User profile management, API key settings
  /api/notifications/* — In-app notifications

Start:
  uvicorn main:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# ── Logging ────────────────────────────────────────────────────────────────── #
logger = logging.getLogger("ss_spark.auth_service")
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
    from database.user_models import init_user_db

    cfg = get_settings()

    _DEFAULT_SECRET = "changeme-please-use-a-long-random-secret-in-production"
    if len(cfg.JWT_SECRET_KEY) < 32 or cfg.JWT_SECRET_KEY == _DEFAULT_SECRET:
        logger.critical("SECURITY: JWT_SECRET_KEY is too weak or still the default placeholder!")

    logger.info("=" * 60)
    logger.info("  SS Spark — Auth Service")
    logger.info("  Swagger UI: http://localhost:8001/docs")
    logger.info("=" * 60)

    # ── Connect to MongoDB (user collections only) ── #
    from motor.motor_asyncio import AsyncIOMotorClient

    masked_uri = re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", cfg.MONGO_URI)
    logger.info("Connecting to MongoDB at: %s (db: %s)", masked_uri, cfg.MONGO_DB_NAME)
    try:
        _client = AsyncIOMotorClient(
            cfg.MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000
        )
        await _client.admin.command("ping")
        _db = _client[cfg.MONGO_DB_NAME]
        await init_user_db(_db)
        logger.info("MongoDB connected and user indexes initialized.")
    except Exception as exc:
        logger.warning("MongoDB not available (%s) — using in-memory fallback.", exc)

    logger.info("Auth Service ready ✓")
    yield
    logger.info("Shutting down Auth Service.")


# ── App ────────────────────────────────────────────────────────────────────── #
app = FastAPI(
    title="SS SPARK — Auth Service",
    description=(
        "Authentication, user management, and notifications microservice for SS SPARK. "
        "Handles registration, login, OAuth, password reset, profile management."
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
from api.auth import router as auth_router
from api.users import router as users_router
from api.notifications import router as notifications_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(notifications_router)


# ── Health ─────────────────────────────────────────────────────────────────── #
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health():
    """Auth Service health check."""
    return {"status": "ok", "service": "auth-service"}


@app.get("/", tags=["Root"])
async def root():
    return {"message": "SS SPARK Auth Service is running.", "docs": "/docs"}


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
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
