"""
api/auth.py
Authentication and user authorization API endpoints for SS SPARK.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field


from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_optional_user,
    hash_password,
    verify_password,
)
from database.user_models import (
    AuthProvider,
    LogAction,
    UserRecord,
    UserRole,
    UserStatus,
    create_user,
    get_user_by_email,
    get_user_by_id,
    record_audit_log,
    update_user,
)
from services.notification_service import send_password_reset_email, send_verification_email
from services.password_reset_service import (
    TokenError,
    check_rate_limit,
    create_reset_token,
    validate_and_consume_token,
)

logger = logging.getLogger("ss_spark.auth_api")
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# --------------------------------------------------------------------------- #
# Request Schemas
# --------------------------------------------------------------------------- #

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: Optional[str] = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResendResetRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


class VerifyEmailRequest(BaseModel):
    token: str


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


def _format_user_response(user: UserRecord, access_token: str = "", refresh_token: str = "") -> Dict[str, Any]:
    """Format user record to match frontend Auth contracts."""
    res = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name or (user.email.split("@")[0] if user.email else "User"),
        "avatar_url": user.avatar_url or "",
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "status": user.status.value if hasattr(user.status, "value") else str(user.status),
        "email_verified": user.email_verified,
        "provider": user.provider.value if hasattr(user.provider, "value") else str(user.provider),
        "created_at": user.created_at,
        "total_documents": 0,
        "total_questions": 0,
        "storage_used_mb": 0.0,
    }
    if access_token:
        res["access_token"] = access_token
    if refresh_token:
        res["refresh_token"] = refresh_token
    return res


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    """Register a new user account."""
    existing = await get_user_by_email(req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # First registered user becomes admin
    user_record = UserRecord(
        email=req.email.lower().strip(),
        full_name=req.full_name or req.email.split("@")[0],
        hashed_password=hash_password(req.password),
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        provider=AuthProvider.LOCAL,
    )
    created = await create_user(user_record)

    token_ver = getattr(created, "token_version", 1)
    access_token = create_access_token({"sub": created.id, "email": created.email, "role": created.role})
    refresh_token = create_refresh_token({"sub": created.id, "email": created.email, "token_version": token_ver})

    await record_audit_log(created.id, LogAction.REGISTER, f"User registered with email: {created.email}")

    return {
        "success": True,
        "message": "Account created successfully.",
        "data": _format_user_response(created, access_token, refresh_token),
    }


@router.post("/login")
async def login(req: LoginRequest):
    """Authenticate with email and password."""
    user = await get_user_by_email(req.email)
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not verify_password(req.password, user.hashed_password):
        await record_audit_log(user.id, LogAction.LOGIN_FAILED, "Failed password attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended. Please contact support.",
        )

    token_ver = getattr(user, "token_version", 1)
    access_token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    refresh_token = create_refresh_token({"sub": user.id, "email": user.email, "token_version": token_ver})

    await record_audit_log(user.id, LogAction.LOGIN, "User logged in successfully")

    return {
        "success": True,
        "message": "Login successful.",
        "data": _format_user_response(user, access_token, refresh_token),
    }


@router.post("/refresh")
async def refresh_tokens(req: RefreshRequest):
    """Obtain a new access token using a valid refresh token with revocation check."""
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    user_id = payload.get("sub")
    user = await get_user_by_id(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    # Validate token_version to ensure revoked tokens cannot be used
    token_ver = payload.get("token_version", 1)
    current_ver = getattr(user, "token_version", 1)
    if token_ver != current_ver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or expired. Please log in again.",
        )

    new_access = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    return {
        "success": True,
        "data": {
            "access_token": new_access,
        },
    }


@router.get("/me")
async def get_profile(current_user: UserRecord = Depends(get_current_user)):
    """Return the authenticated user profile."""
    return {
        "success": True,
        "data": _format_user_response(current_user),
    }


@router.patch("/me")
async def update_profile(
    req: UpdateProfileRequest,
    current_user: UserRecord = Depends(get_current_user),
):
    """Update profile details."""
    updates: Dict[str, Any] = {}
    if req.full_name is not None:
        updates["full_name"] = req.full_name
    if req.avatar_url is not None:
        updates["avatar_url"] = req.avatar_url

    if updates:
        await update_user(current_user.id, updates)
        updated = await get_user_by_id(current_user.id)
        if updated:
            current_user = updated

    return {
        "success": True,
        "data": _format_user_response(current_user),
    }


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, request: Request):
    """
    Initiate a secure password-reset flow.

    Security:
    - Never reveals whether the email exists (anti-enumeration).
    - Rate-limited: 3 requests per 10 minutes per email+IP.
    - Token: cryptographically random, hashed in DB, expires 30 minutes, single-use.
    """
    logger.info("[forgot-password] Request received for email domain: %s",
                req.email.split('@')[-1] if '@' in req.email else 'invalid')

    # Rate-limit check (anti-abuse)
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)
    allowed, retry_after = check_rate_limit(req.email, client_ip)
    if not allowed:
        logger.warning(
            "[forgot-password] Rate limit hit for email domain: %s ip: %s",
            req.email.split('@')[-1] if '@' in req.email else '?', client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many reset requests. Please wait {retry_after} seconds before trying again.",
            headers={"Retry-After": str(retry_after)},
        )

    # Look up user — do NOT short-circuit the response based on existence
    user = await get_user_by_email(req.email)
    logger.info("[forgot-password] User lookup complete. Found: %s", user is not None)

    if user:
        try:
            # Generate secure single-use token
            logger.info("[forgot-password] Generating reset token for user_id=%s", user.id)
            raw_token = await create_reset_token(user.id, user.email)
            logger.info("[forgot-password] Reset token generated and stored.")

            # Send the email
            logger.info("[forgot-password] Initiating email send to %s", user.email)
            email_sent = await send_password_reset_email(user.email, raw_token)

            if email_sent:
                logger.info("[forgot-password] Email sent successfully.")
            else:
                logger.error(
                    "[forgot-password] Email delivery failed for user_id=%s. "
                    "Check EMAIL_PROVIDER / RESEND_API_KEY / SMTP settings.",
                    user.id
                )
        except Exception as exc:
            logger.exception("[forgot-password] Unexpected error during token/email: %s", exc)

    # Always return the same generic response regardless of outcome
    # This prevents account enumeration attacks
    return {
        "success": True,
        "message": "If an account exists for this email, a password reset link has been sent. Check your spam folder if you don't see it.",
    }


@router.post("/resend-reset-link")
async def resend_reset_link(req: ResendResetRequest, request: Request):
    """
    Resend a password-reset email.

    Subject to the same rate limit as /forgot-password.
    Invalidates the previous token and issues a new one.
    """
    logger.info("[resend-reset] Request received")

    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)
    allowed, retry_after = check_rate_limit(req.email, client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await get_user_by_email(req.email)
    if user:
        try:
            raw_token = await create_reset_token(user.id, user.email)
            email_sent = await send_password_reset_email(user.email, raw_token)
            if not email_sent:
                logger.error("[resend-reset] Email delivery failed for user_id=%s", user.id)
        except Exception as exc:
            logger.exception("[resend-reset] Error: %s", exc)

    return {
        "success": True,
        "message": "If an account exists for this email, a new reset link has been sent.",
    }


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """
    Reset password using a secure single-use token.

    Security:
    - Validates token hash against stored hash (never stores raw token).
    - Checks expiry and consumed status.
    - Revokes all existing sessions (token_version bump).
    """
    logger.info("[reset-password] Request received.")

    try:
        user_id = await validate_and_consume_token(req.token)
    except TokenError as exc:
        logger.info("[reset-password] Token validation failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            headers={"X-Token-Expired": "true" if exc.is_expired else "false"},
        ) from exc

    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account not found."
        )

    # Update password and invalidate all existing sessions
    new_ver = getattr(user, "token_version", 1) + 1
    await update_user(user.id, {
        "hashed_password": hash_password(req.new_password),
        "token_version": new_ver,
    })
    await record_audit_log(user.id, LogAction.PASSWORD_RESET, "Password reset via secure token")
    logger.info("[reset-password] Password updated for user_id=%s", user_id)

    return {
        "success": True,
        "message": "Your password has been reset successfully. You can now log in with your new password.",
    }


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest):
    """Verify user's email address."""
    payload = decode_token(req.token)
    user_id = payload.get("sub")
    user = await get_user_by_id(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token.")

    await update_user(user.id, {"email_verified": True})
    return {
        "success": True,
        "message": "Email address verified successfully.",
    }


@router.post("/logout")
async def logout(current_user: Optional[UserRecord] = Depends(get_optional_user)):
    """Log out current user and revoke their refresh tokens."""
    if current_user:
        new_ver = getattr(current_user, "token_version", 1) + 1
        await update_user(current_user.id, {"token_version": new_ver})
        await record_audit_log(current_user.id, LogAction.LOGOUT, "User logged out")
    return {
        "success": True,
        "message": "Logged out successfully.",
    }


# --------------------------------------------------------------------------- #
# OAuth Endpoints
# --------------------------------------------------------------------------- #

from fastapi import Request
from fastapi.responses import RedirectResponse
import urllib.parse
import httpx
from core.config import get_settings
from database.user_models import get_user_by_provider


@router.get("/oauth/config")
async def oauth_config():
    """Return public OAuth configuration status without exposing secrets."""
    cfg = get_settings()
    return {
        "success": True,
        "data": {
            "google_enabled": cfg.has_oauth_google,
            "github_enabled": cfg.has_oauth_github,
            "google_client_id": cfg.GOOGLE_CLIENT_ID if cfg.has_oauth_google else "",
        },
    }


def _build_oauth_redirect_uri(request: Request) -> str:
    """Construct the Google OAuth redirect URI respecting proxy headers and HTTPS."""
    proto = request.headers.get("x-forwarded-proto", "")
    base = str(request.base_url).rstrip("/")
    if proto == "https" and base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    return f"{base}/api/auth/oauth/google/callback"


@router.get("/oauth/google")
async def oauth_google_redirect(request: Request):
    """Redirect to Google OAuth consent screen or redirect to login with clear error if not configured."""
    cfg = get_settings()
    frontend_url = cfg.FRONTEND_URL.rstrip("/")
    if not cfg.has_oauth_google:
        return RedirectResponse(
            url=f"{frontend_url}/login?error={urllib.parse.quote('Google OAuth is not configured in backend .env. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET, or use email/password login.')}"
        )

    redirect_uri = _build_oauth_redirect_uri(request)
    params = {
        "client_id": cfg.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=url)


@router.get("/oauth/google/callback")
async def oauth_google_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None):
    """Handle Google OAuth callback and redirect to frontend with tokens in hash fragment."""
    cfg = get_settings()
    frontend_url = cfg.FRONTEND_URL.rstrip("/")

    if error or not code:
        err_msg = error or "Authorization code missing"
        return RedirectResponse(url=f"{frontend_url}/login?error={urllib.parse.quote(err_msg)}")

    redirect_uri = _build_oauth_redirect_uri(request)

    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": cfg.GOOGLE_CLIENT_ID,
                    "client_secret": cfg.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                logger.error("Google token exchange failed: %s", token_resp.text)
                return RedirectResponse(url=f"{frontend_url}/login?error=Google+token+exchange+failed")

            token_data = token_resp.json()
            access_tok = token_data.get("access_token")

            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_tok}"},
            )
            if userinfo_resp.status_code != 200:
                logger.error("Google userinfo fetch failed: %s", userinfo_resp.text)
                return RedirectResponse(url=f"{frontend_url}/login?error=Failed+to+fetch+user+profile")

            userinfo = userinfo_resp.json()
            google_id = str(userinfo.get("id"))
            email = (userinfo.get("email") or "").lower().strip()
            name = userinfo.get("name") or email.split("@")[0]
            picture = userinfo.get("picture") or ""

            if not email:
                return RedirectResponse(url=f"{frontend_url}/login?error=Google+account+missing+email")

            user = await get_user_by_provider(AuthProvider.GOOGLE, google_id)
            if not user:
                user = await get_user_by_email(email)
                if user:
                    await update_user(user.id, {
                        "provider": AuthProvider.GOOGLE.value,
                        "provider_id": google_id,
                        "avatar_url": user.avatar_url or picture,
                        "email_verified": True,
                    })
                    user = await get_user_by_id(user.id)
                else:
                    new_user = UserRecord(
                        email=email,
                        full_name=name,
                        avatar_url=picture,
                        provider=AuthProvider.GOOGLE,
                        provider_id=google_id,
                        email_verified=True,
                        role=UserRole.USER,
                        status=UserStatus.ACTIVE,
                    )
                    user = await create_user(new_user)

            if not user:
                return RedirectResponse(url=f"{frontend_url}/login?error=Failed+to+create+user")

            role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
            jwt_access = create_access_token({"sub": user.id, "email": user.email, "role": role_val})
            token_ver = getattr(user, "token_version", 1)
            jwt_refresh = create_refresh_token({"sub": user.id, "email": user.email, "token_version": token_ver})

            await record_audit_log(user.id, LogAction.LOGIN, "User logged in via Google OAuth")

            return RedirectResponse(
                url=f"{frontend_url}/auth/callback#access_token={jwt_access}&refresh_token={jwt_refresh}"
            )
    except Exception as e:
        logger.exception("Unexpected OAuth error: %s", e)
        return RedirectResponse(url=f"{frontend_url}/login?error={urllib.parse.quote(str(e))}")

