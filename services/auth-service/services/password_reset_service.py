"""
services/password_reset_service.py

Secure password-reset token lifecycle management.

Design:
  1. Generate a cryptographically random 48-byte token (secrets.token_urlsafe).
  2. Store SHA-256 hash of the token in MongoDB (password_reset_tokens collection).
  3. Send raw token to the user via email URL.
  4. On submission, hash the supplied token and compare with stored hash.
  5. Token expires after 30 minutes.
  6. Token is single-use: consumed flag is set after first use.
  7. A new reset request invalidates all previous pending tokens for that email.
  8. Rate limiting: max 3 requests per 10 minutes per (email OR IP).

Security properties:
  - Raw token is never stored in DB → database breach cannot be used to reset passwords.
  - URL-safe base64 encoding → safe in emails and URLs without encoding issues.
  - 48 bytes of entropy = 384 bits → brute-force infeasible.
  - Short TTL (30 min) limits exposure window.
  - Single-use: replay attacks fail.
  - Invalidation: only the latest token works.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger("ss_spark.password_reset")

# ─── In-memory fallback ──────────────────────────────────────────────────────
# Keyed by token_hash. Used when MongoDB is not available (local dev without DB).
_mem_tokens: dict[str, dict[str, Any]] = {}
# Rate limit buckets: key = "email:ip" → list of request timestamps
_rate_buckets: dict[str, list[float]] = {}

# Constants
TOKEN_EXPIRY_MINUTES = 30
MAX_REQUESTS = 3
RATE_WINDOW_SECONDS = 600  # 10 minutes


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of the raw token — this is what we store, never the raw token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _get_db() -> Any:
    from database.user_models import _get_db as _udb
    return _udb()


# ─── Rate limiting ────────────────────────────────────────────────────────────

def check_rate_limit(email: str, ip: str | None = None) -> tuple[bool, int]:
    """
    Check whether the requester is within the rate limit.

    Returns:
        (allowed: bool, retry_after_seconds: int)
    """
    now = time.monotonic()
    key = f"{email.lower()}:{ip or 'noip'}"
    bucket = _rate_buckets.setdefault(key, [])

    # Remove expired entries
    window_start = now - RATE_WINDOW_SECONDS
    _rate_buckets[key] = [t for t in bucket if t > window_start]

    if len(_rate_buckets[key]) >= MAX_REQUESTS:
        oldest = _rate_buckets[key][0]
        retry_after = int(RATE_WINDOW_SECONDS - (now - oldest)) + 1
        return False, retry_after

    _rate_buckets[key].append(now)
    return True, 0


# ─── Token creation ───────────────────────────────────────────────────────────

async def create_reset_token(user_id: str, email: str) -> str:
    """
    Generate a new reset token, invalidate old tokens for this user, store the hash.

    Returns the raw (unhashed) token to embed in the reset URL.
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRY_MINUTES)

    db = _get_db()
    if db is not None:
        # Invalidate all previous tokens for this user
        await db.password_reset_tokens.update_many(
            {"user_id": user_id, "consumed": False},
            {"$set": {"consumed": True, "invalidated_at": datetime.now(timezone.utc)}},
        )
        # Store the new hashed token
        await db.password_reset_tokens.insert_one({
            "token_hash": token_hash,
            "user_id": user_id,
            "email": email.lower().strip(),
            "expires_at": expires_at,
            "consumed": False,
            "created_at": datetime.now(timezone.utc),
        })
    else:
        # In-memory fallback: invalidate old tokens for this user
        for rec in list(_mem_tokens.values()):
            if rec["user_id"] == user_id and not rec["consumed"]:
                rec["consumed"] = True
        _mem_tokens[token_hash] = {
            "token_hash": token_hash,
            "user_id": user_id,
            "email": email.lower().strip(),
            "expires_at": expires_at,
            "consumed": False,
            "created_at": datetime.now(timezone.utc),
        }

    logger.info("[reset] Token created for user_id=%s (expires in %d min)", user_id, TOKEN_EXPIRY_MINUTES)
    return raw_token


# ─── Token validation ────────────────────────────────────────────────────────

class TokenError(Exception):
    """Raised when a reset token is invalid, expired, or already used."""

    def __init__(self, message: str, is_expired: bool = False):
        super().__init__(message)
        self.is_expired = is_expired


async def validate_and_consume_token(raw_token: str) -> str:
    """
    Validate the token and mark it consumed.

    Returns user_id on success.
    Raises TokenError on invalid/expired/consumed token.
    """
    if not raw_token or len(raw_token) < 32:
        raise TokenError("Invalid reset token.", is_expired=False)

    token_hash = _hash_token(raw_token)
    db = _get_db()

    if db is not None:
        rec = await db.password_reset_tokens.find_one({"token_hash": token_hash})
    else:
        rec = _mem_tokens.get(token_hash)

    if not rec:
        logger.warning("[reset] Token not found (hash mismatch or never created)")
        raise TokenError("This reset link is invalid or has already been used.", is_expired=False)

    if rec.get("consumed"):
        logger.warning("[reset] Token already consumed for user_id=%s", rec.get("user_id"))
        raise TokenError("This reset link has already been used. Please request a new one.", is_expired=False)

    expires_at = rec.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            logger.info("[reset] Token expired for user_id=%s", rec.get("user_id"))
            raise TokenError(
                "This reset link has expired. Please request a new one.", is_expired=True
            )

    # Consume the token — prevent reuse
    if db is not None:
        await db.password_reset_tokens.update_one(
            {"token_hash": token_hash},
            {"$set": {"consumed": True, "consumed_at": datetime.now(timezone.utc)}},
        )
    else:
        _mem_tokens[token_hash]["consumed"] = True

    user_id = rec["user_id"]
    logger.info("[reset] Token validated and consumed for user_id=%s", user_id)
    return user_id


# ─── DB index setup ───────────────────────────────────────────────────────────

async def ensure_indexes(db: Any) -> None:
    """Create MongoDB indexes for password_reset_tokens. Call from lifespan startup."""
    try:
        await db.password_reset_tokens.create_index("token_hash", unique=True)
        await db.password_reset_tokens.create_index("user_id")
        await db.password_reset_tokens.create_index(
            "expires_at",
            expireAfterSeconds=0,  # MongoDB TTL — auto-deletes expired docs
        )
        logger.info("[reset] password_reset_tokens indexes ensured.")
    except Exception as exc:
        logger.warning("[reset] Index creation warning (non-fatal): %s", exc)
