"""
test_security_audit_fixes.py
Comprehensive automated test suite for SS-SPARK security & multi-tenant fixes:
  - SEC-01: Admin-only protection on /api/users/settings (No regular user key hijacking)
  - SEC-02: Strict user_id ownership on DELETE & PATCH /api/sessions/{id}
  - SEC-03: CORS restriction to SS-SPARK domains
  - SEC-04: Chat history isolation (No cross-tenant or unauthenticated leakage)
  - UPL-01: User-scoped SHA-256 upload deduplication
  - RAT-01: Per-IP Chat endpoint rate limiting (HTTP 429)
  - MOD-01: Gemini candidate model list verification
"""

import io
import time
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from main import app
from core.security import create_access_token, hash_password
from database.models import ChatMessage, ChatSession, UploadedDoc, create_session, save_document, save_message
from database.user_models import UserRecord, UserRole, UserStatus, _mem_users


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_a():
    uid = f"user_a_{uuid.uuid4().hex[:6]}"
    u = UserRecord(
        id=uid,
        email=f"{uid}@example.com",
        username=uid,
        password_hash=hash_password("Password123!"),
        full_name="User Alpha",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    _mem_users[uid] = u
    token = create_access_token({"sub": uid, "role": "user", "token_version": 1})
    return {"user": u, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def user_b():
    uid = f"user_b_{uuid.uuid4().hex[:6]}"
    u = UserRecord(
        id=uid,
        email=f"{uid}@example.com",
        username=uid,
        password_hash=hash_password("Password123!"),
        full_name="User Beta",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    _mem_users[uid] = u
    token = create_access_token({"sub": uid, "role": "user", "token_version": 1})
    return {"user": u, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def admin_user():
    uid = f"admin_{uuid.uuid4().hex[:6]}"
    u = UserRecord(
        id=uid,
        email=f"{uid}@example.com",
        username=uid,
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin User",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    _mem_users[uid] = u
    token = create_access_token({"sub": uid, "role": "admin", "token_version": 1})
    return {"user": u, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


# ─── SEC-01: Settings Authorization ──────────────────────────────────────────

def test_sec01_normal_user_cannot_update_settings(client, user_a):
    """Normal authenticated users must be forbidden (403) from updating global settings."""
    res = client.post(
        "/api/users/settings",
        json={"gemini_api_key": "fake_malicious_key_123"},
        headers=user_a["headers"],
    )
    assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
    assert "Administrator privileges required" in res.json().get("detail", "")


def test_sec01_admin_can_update_settings(client, admin_user):
    """Admin users are authorized to update system settings."""
    res = client.post(
        "/api/users/settings",
        json={"gemini_api_key": "valid_admin_key_test"},
        headers=admin_user["headers"],
    )
    assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}: {res.text}"
    assert res.json().get("success") is True


def test_sec01_get_settings_does_not_leak_raw_keys(client, user_a):
    """GET /api/users/settings returns boolean metadata only, never raw API keys."""
    res = client.get("/api/users/settings", headers=user_a["headers"])
    assert res.status_code == 200
    data = res.json().get("data", {})
    assert "has_gemini" in data
    assert "gemini_api_key" not in data
    assert "openai_api_key" not in data


# ─── SEC-02: Session IDOR & Ownership ────────────────────────────────────────

@pytest.mark.asyncio
async def test_sec02_unauthenticated_cannot_delete_session(client):
    """Unauthenticated DELETE on session returns 401."""
    res = client.delete("/api/sessions/any_session_id")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_sec02_user_a_cannot_delete_user_b_session(client, user_a, user_b):
    """User A attempting to delete User B's session receives 404 (IDOR blocked)."""
    # Create session for User B
    session_b = ChatSession(user_id=user_b["user"].id, title="User B Secret Chat")
    await create_session(session_b)

    # User A tries to delete User B's session
    res = client.delete(f"/api/sessions/{session_b.id}", headers=user_a["headers"])
    assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"

    # User B can delete own session
    res_b = client.delete(f"/api/sessions/{session_b.id}", headers=user_b["headers"])
    assert res_b.status_code == 200


@pytest.mark.asyncio
async def test_sec02_user_a_cannot_modify_user_b_session(client, user_a, user_b):
    """User A cannot rename or modify User B's session."""
    session_b = ChatSession(user_id=user_b["user"].id, title="User B Original Title")
    await create_session(session_b)

    res = client.patch(
        f"/api/sessions/{session_b.id}",
        json={"title": "Hacked Title"},
        headers=user_a["headers"],
    )
    assert res.status_code == 404


# ─── SEC-04: Chat History Isolation ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_sec04_user_a_cannot_read_user_b_history(client, user_a, user_b):
    """User A cannot retrieve User B's messages even with session_id known."""
    session_b = ChatSession(user_id=user_b["user"].id, title="User B Confidential")
    await create_session(session_b)

    msg_b = ChatMessage(
        session_id=session_b.id,
        role="user",
        content="Confidential financial analysis question",
        user_id=user_b["user"].id,
    )
    await save_message(msg_b)

    # User A queries session_b history
    res = client.get(f"/api/history?session_id={session_b.id}", headers=user_a["headers"])
    assert res.status_code == 200
    assert len(res.json().get("data", [])) == 0, "User A must not receive User B's messages"

    # User B queries session_b history
    res_b = client.get(f"/api/history?session_id={session_b.id}", headers=user_b["headers"])
    assert res_b.status_code == 200
    assert len(res_b.json().get("data", [])) == 1


@pytest.mark.asyncio
async def test_sec04_unauthenticated_cannot_read_registered_history(client, user_b):
    """Unauthenticated request with a valid registered session_id returns 0 messages."""
    session_b = ChatSession(user_id=user_b["user"].id, title="User B Private")
    await create_session(session_b)

    msg_b = ChatMessage(
        session_id=session_b.id,
        role="user",
        content="Secret query",
        user_id=user_b["user"].id,
    )
    await save_message(msg_b)

    res = client.get(f"/api/history?session_id={session_b.id}")
    assert res.status_code == 200
    assert len(res.json().get("data", [])) == 0


# ─── UPL-01: SHA-256 Upload Deduplication ─────────────────────────────────────

def test_upl01_same_user_duplicate_upload_deduplicated(client, user_a):
    """Same user uploading exact same content returns existing document without duplicate work."""
    file_bytes = b"Sample exam content for deduplication test: Question 1. Define Operating System."
    
    # 1st Upload
    res1 = client.post(
        "/api/upload",
        files={"files": ("exam_v1.txt", io.BytesIO(file_bytes), "text/plain")},
        headers=user_a["headers"],
    )
    assert res1.status_code == 200
    data1 = res1.json()["data"][0]
    doc_id_1 = data1["id"]

    # 2nd Upload with identical bytes
    res2 = client.post(
        "/api/upload",
        files={"files": ("exam_v2_dup.txt", io.BytesIO(file_bytes), "text/plain")},
        headers=user_a["headers"],
    )
    assert res2.status_code == 200
    data2 = res2.json()["data"][0]
    doc_id_2 = data2["id"]

    assert doc_id_1 == doc_id_2, "Duplicate upload by same user should reuse existing document ID"
    assert "already indexed" in data2.get("message", "").lower()


def test_upl01_different_users_same_content_isolated(client, user_a, user_b):
    """User A and User B uploading identical content get separate isolated document records."""
    file_bytes = b"Shared textbook chapter content for tenant isolation test."
    
    # User A upload
    res_a = client.post(
        "/api/upload",
        files={"files": ("shared.txt", io.BytesIO(file_bytes), "text/plain")},
        headers=user_a["headers"],
    )
    assert res_a.status_code == 200
    doc_a_id = res_a.json()["data"][0]["id"]

    # User B upload
    res_b = client.post(
        "/api/upload",
        files={"files": ("shared.txt", io.BytesIO(file_bytes), "text/plain")},
        headers=user_b["headers"],
    )
    assert res_b.status_code == 200
    doc_b_id = res_b.json()["data"][0]["id"]

    assert doc_a_id != doc_b_id, "Different users must have isolated document IDs even for identical content"


# ─── RAT-01: Chat Rate Limiting ──────────────────────────────────────────────

def test_rat01_chat_rate_limiting(client, monkeypatch):
    """Exceeding chat rate limit triggers HTTP 429."""
    from api.chat import _chat_rate_buckets
    import api.chat as chat_module
    _chat_rate_buckets.clear()

    async def mock_ask(*args, **kwargs):
        return {"answer": "mocked", "status": "success"}

    monkeypatch.setattr(chat_module, "ask_question", mock_ask)

    hit_429 = False
    for i in range(35):
        res = client.post("/api/chat?stream=false", json={"question": f"Test question {i}"})
        if res.status_code == 429:
            hit_429 = True
            assert "Rate limit exceeded" in res.json().get("detail", "")
            assert "Retry-After" in res.headers
            break

    assert hit_429, "Rate limiter should return 429 after exceeding limit"
    _chat_rate_buckets.clear()


# ─── SEC-03: CORS Scoped Origin Verification ─────────────────────────────────

def test_sec03_cors_origin_policy():
    """Verify CORS regex rejects random third-party domains and accepts official SS-SPARK domains."""
    import re
    from main import app
    from fastapi.middleware.cors import CORSMiddleware

    # Find CORS middleware
    cors = None
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            cors = middleware
            break

    assert cors is not None
    regex_pattern = getattr(cors, "kwargs", {}).get("allow_origin_regex") or getattr(cors, "options", {}).get("allow_origin_regex")
    assert regex_pattern is not None

    # Test allowed patterns
    assert re.match(regex_pattern, "https://ss-spark.vercel.app")
    assert re.match(regex_pattern, "https://ss-spark-git-main-user.vercel.app")
    assert re.match(regex_pattern, "https://preview.ss-spark.vercel.app")

    # Test rejected patterns (SEC-03 Fix)
    assert not re.match(regex_pattern, "https://malicious-site.vercel.app")
    assert not re.match(regex_pattern, "https://evil-hacker.vercel.app")
    assert not re.match(regex_pattern, "https://arbitrary-app.com")


# ─── MOD-01: Candidate Models ────────────────────────────────────────────────

def test_mod01_gemini_candidate_models():
    """Verify GEMINI_MODELS candidate list in general_llm."""
    from rag.general_llm import GEMINI_MODELS
    assert "gemini/gemini-2.0-flash" in GEMINI_MODELS
    assert "gemini/gemini-2.0-flash-lite" in GEMINI_MODELS
