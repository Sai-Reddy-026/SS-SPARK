"""
api/auth.py
Authentication and user authorization API endpoints for SS SPARK.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from database.user_models import (
    AuthProvider,
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

    access_token = create_access_token({"sub": created.id, "email": created.email, "role": created.role})
    refresh_token = create_refresh_token({"sub": created.id, "email": created.email})

    await record_audit_log(created.id, "register", f"User registered with email: {created.email}")

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
        await record_audit_log(user.id, "login_failed", "Failed password attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended. Please contact support.",
        )

    access_token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    refresh_token = create_refresh_token({"sub": user.id, "email": user.email})

    await record_audit_log(user.id, "login", "User logged in successfully")

    return {
        "success": True,
        "message": "Login successful.",
        "data": _format_user_response(user, access_token, refresh_token),
    }


@router.post("/refresh")
async def refresh_tokens(req: RefreshRequest):
    """Obtain a new access token using a valid refresh token."""
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    user_id = payload.get("sub")
    user = await get_user_by_id(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

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
async def forgot_password(req: ForgotPasswordRequest):
    """Initiate a password reset flow."""
    user = await get_user_by_email(req.email)
    if user:
        reset_tok = create_access_token({"sub": user.id, "action": "reset_password"})
        await send_password_reset_email(user.email, reset_tok)
    return {
        "success": True,
        "message": "If an account with this email exists, a password reset link has been dispatched.",
    }


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Reset password using a reset token."""
    payload = decode_token(req.token)
    user_id = payload.get("sub")
    user = await get_user_by_id(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token or user.")

    await update_user(user.id, {"hashed_password": hash_password(req.new_password)})
    await record_audit_log(user.id, "password_reset", "Password reset successfully")
    return {
        "success": True,
        "message": "Password has been successfully updated. You can now log in.",
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
async def logout(current_user: Optional[UserRecord] = Depends(get_current_user)):
    """Log out current user."""
    if current_user:
        await record_audit_log(current_user.id, "logout", "User logged out")
    return {
        "success": True,
        "message": "Logged out successfully.",
    }
