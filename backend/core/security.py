"""
core/security.py
Production security and authentication utilities for SS SPARK.

Features:
- Direct bcrypt password hashing with SHA-256 pre-hashing (bulletproof against long inputs & passlib bug)
- JWT access and refresh token generation & verification using python-jose
- FastAPI dependency injection (get_current_user, get_current_admin, get_optional_user)
- Dynamic CORS origin resolution
- Runtime API key management
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.config import Settings, get_settings
from database.user_models import UserRecord, UserRole, UserStatus, get_user_by_email, get_user_by_id

logger = logging.getLogger("ss_spark.security")

# Optional Bearer schema — auto_error=False allows public endpoints with optional user context
oauth2_scheme = HTTPBearer(auto_error=False)


# --------------------------------------------------------------------------- #
# Password Hashing (Direct bcrypt + SHA-256 Pre-hashing)
# --------------------------------------------------------------------------- #

def _prehash(password: str) -> bytes:
    """Pre-hash password with SHA-256 to support arbitrary lengths safely."""
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    prehashed = _prehash(password)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(prehashed, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        prehashed = _prehash(plain_password)
        return bcrypt.checkpw(prehashed, hashed_password.encode("utf-8"))
    except Exception as exc:
        logger.warning("Password verification failed with error: %s", exc)
        return False


# --------------------------------------------------------------------------- #
# JWT Token Management
# --------------------------------------------------------------------------- #

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    settings: Optional[Settings] = None,
) -> str:
    """Create a signed JWT access token."""
    cfg = settings or get_settings()
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=cfg.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "access",
    })
    return jwt.encode(to_encode, cfg.JWT_SECRET_KEY, algorithm=cfg.JWT_ALGORITHM)


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    settings: Optional[Settings] = None,
) -> str:
    """Create a signed JWT refresh token."""
    cfg = settings or get_settings()
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=cfg.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "refresh",
    })
    return jwt.encode(to_encode, cfg.JWT_SECRET_KEY, algorithm=cfg.JWT_ALGORITHM)


def decode_token(token: str, settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Decode and validate a signed JWT token."""
    cfg = settings or get_settings()
    try:
        payload = jwt.decode(token, cfg.JWT_SECRET_KEY, algorithms=[cfg.JWT_ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# --------------------------------------------------------------------------- #
# FastAPI Authentication Dependencies
# --------------------------------------------------------------------------- #

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    settings: Settings = Depends(get_settings),
) -> Optional[UserRecord]:
    """Return the authenticated UserRecord if a valid Bearer token is provided, else None."""
    if not credentials:
        return None

    try:
        payload = decode_token(credentials.credentials, settings)
        user_id = payload.get("sub") or payload.get("id")
        email = payload.get("email")

        user: Optional[UserRecord] = None
        if user_id:
            user = await get_user_by_id(user_id)
        if not user and email:
            user = await get_user_by_email(email)

        return user
    except HTTPException:
        return None
    except Exception as exc:
        logger.debug("Optional auth check encountered exception: %s", exc)
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    settings: Settings = Depends(get_settings),
) -> UserRecord:
    """FastAPI dependency: require a valid authenticated active user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials, settings)
    token_type = payload.get("type", "access")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for authorization. Please use an access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub") or payload.get("id")
    email = payload.get("email")

    user: Optional[UserRecord] = None
    if user_id:
        user = await get_user_by_id(user_id)
    if not user and email:
        user = await get_user_by_email(email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with this token was not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended. Please contact administration.",
        )

    return user


async def get_current_admin(
    current_user: UserRecord = Depends(get_current_user),
) -> UserRecord:
    """FastAPI dependency: require an authenticated user with ADMIN role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to access this resource.",
        )
    return current_user


# --------------------------------------------------------------------------- #
# CORS & Runtime Key Management Helpers
# --------------------------------------------------------------------------- #

def get_cors_origins(settings: Settings) -> List[str]:
    """Return deduplicated list of allowed CORS origins, including FRONTEND_URL."""
    origins = set(settings.ALLOWED_ORIGINS)
    if settings.FRONTEND_URL:
        origins.add(settings.FRONTEND_URL.rstrip("/"))
    # Common local addresses
    origins.update([
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ])
    return list(origins)


def update_api_keys(
    openai_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
) -> None:
    """Apply updated API keys to environment variables and settings."""
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key
        os.environ["GOOGLE_API_KEY"] = gemini_api_key
    if anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key
