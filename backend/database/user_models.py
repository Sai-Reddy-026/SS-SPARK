"""
database/user_models.py

MongoDB models for the auth / user management system.

Collections:
  - users            — registered user accounts
  - sessions         — chat sessions (renamed from session_id coupling)
  - oauth_accounts   — linked OAuth providers
  - audit_logs       — security / activity audit trail
  - notifications    — in-app notifications
  - system_settings  — global admin-controlled settings
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_db: Any = None  # motor AsyncIOMotorDatabase — set by init_user_db()


# --------------------------------------------------------------------------- #
# Initialisation
# --------------------------------------------------------------------------- #

async def init_user_db(db: Any) -> None:
    """Receive the shared Motor database and create indexes."""
    global _db
    _db = db

    # Users: unique email + username indexes
    await _db.users.create_index("email", unique=True)
    try:
        # Drop legacy non-sparse username_1 index if it exists
        await _db.users.drop_index("username_1")
    except Exception:
        pass
    await _db.users.create_index("username", unique=True, sparse=True)

    # Sessions: scoped to user
    await _db.chat_sessions.create_index([("user_id", 1), ("updated_at", -1)])

    # Audit logs: time-series style
    try:
        await _db.audit_logs.create_index([("user_id", 1), ("created_at", -1)])
        await _db.audit_logs.create_index("created_at", expireAfterSeconds=60 * 60 * 24 * 90)  # 90-day TTL
    except Exception:
        pass

    # Notifications: per-user
    await _db.notifications.create_index([("user_id", 1), ("created_at", -1)])

    logger.info("User DB indexes created.")


_mem_users: Dict[str, UserRecord] = {}
_mem_sessions: Dict[str, ChatSession] = {}
_mem_logs: List[AuditLog] = []
_mem_notifications: List[Notification] = []
_mem_system_settings: Optional[SystemSettings] = None


def _get_db() -> Any:
    """Return Motor DB or None if in fallback mode."""
    return _db


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class AuthProvider(str, Enum):
    LOCAL = "local"
    GOOGLE = "google"
    GITHUB = "github"


class LogAction(str, Enum):
    REGISTER = "register"
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFIED = "email_verified"
    UPLOAD = "upload"
    DELETE_DOCUMENT = "delete_document"
    ADMIN_ACTION = "admin_action"
    ROLE_CHANGE = "role_change"
    SUSPEND = "suspend"
    ACTIVATE = "activate"


# --------------------------------------------------------------------------- #
# Pydantic models
# --------------------------------------------------------------------------- #

class UserRecord(BaseModel):
    """A registered SS SPARK user."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    username: Optional[str] = None
    full_name: str = ""
    avatar_url: str = ""
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE
    hashed_password: Optional[str] = None            # None for OAuth-only users
    provider: AuthProvider = AuthProvider.LOCAL
    provider_id: Optional[str] = None               # OAuth provider's user ID
    email_verified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None

    # Per-user usage stats (denormalised for quick reads)
    total_documents: int = 0
    total_questions: int = 0
    storage_used_mb: float = 0.0


class OAuthAccount(BaseModel):
    """A linked OAuth account for a user."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    provider: AuthProvider
    provider_id: str
    access_token: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatSession(BaseModel):
    """A named chat conversation belonging to a user."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str = "New Chat"
    pinned: bool = False
    archived: bool = False
    folder: Optional[str] = None
    message_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog(BaseModel):
    """Security / activity audit trail entry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    action: LogAction
    detail: str = ""
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Notification(BaseModel):
    """In-app notification for a user."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str                        # or "broadcast" for all users
    title: str
    body: str
    kind: str = "info"                  # "info" | "success" | "warning" | "error"
    read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SystemSettings(BaseModel):
    """Admin-controlled global system settings (single document)."""
    ocr_engine: str = "tesseract"
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    chunk_size: int = 500
    chunk_overlap: int = 50
    max_upload_size_mb: int = 50
    allowed_file_types: List[str] = Field(
        default=[".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".pptx"]
    )
    rate_limit_requests_per_minute: int = 60
    maintenance_mode: bool = False
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------- #
# CRUD helpers — Users
# --------------------------------------------------------------------------- #

async def create_user(user: UserRecord) -> UserRecord:
    """Insert a new user into MongoDB or in-memory fallback."""
    db = _get_db()
    if db is not None:
        doc = user.model_dump()
        doc["_id"] = doc.pop("id")
        if not doc.get("username"):
            doc.pop("username", None)
        await db.users.insert_one(doc)
    else:
        _mem_users[user.id] = user
    return user


async def get_user_by_email(email: str) -> Optional[UserRecord]:
    """Find a user by email (case-insensitive)."""
    db = _get_db()
    if db is not None:
        doc = await db.users.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}})
        return _doc_to_user(doc) if doc else None
    target = email.lower().strip()
    for u in _mem_users.values():
        if u.email.lower() == target:
            return u
    return None


async def get_user_by_id(user_id: str) -> Optional[UserRecord]:
    """Find a user by their ID."""
    db = _get_db()
    if db is not None:
        doc = await db.users.find_one({"_id": user_id})
        return _doc_to_user(doc) if doc else None
    return _mem_users.get(user_id)


async def get_user_by_provider(provider: AuthProvider, provider_id: str) -> Optional[UserRecord]:
    """Find a user by OAuth provider + provider_id."""
    db = _get_db()
    if db is not None:
        doc = await db.users.find_one({"provider": provider.value, "provider_id": provider_id})
        return _doc_to_user(doc) if doc else None
    for u in _mem_users.values():
        if u.provider == provider and u.provider_id == provider_id:
            return u
    return None


async def update_user(user_id: str, updates: dict) -> None:
    """Apply a partial update to a user document."""
    db = _get_db()
    if db is not None:
        updates["updated_at"] = datetime.now(timezone.utc)
        await db.users.update_one({"_id": user_id}, {"$set": updates})
    else:
        user = _mem_users.get(user_id)
        if user:
            data = user.model_dump()
            data.update(updates)
            data["updated_at"] = datetime.now(timezone.utc)
            _mem_users[user_id] = UserRecord(**data)


async def list_users(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
) -> tuple[List[UserRecord], int]:
    """Return paginated list of users with optional filters."""
    db = _get_db()
    if db is not None:
        query: dict[str, Any] = {}
        if search:
            query["$or"] = [
                {"email": {"$regex": search, "$options": "i"}},
                {"full_name": {"$regex": search, "$options": "i"}},
            ]
        if role:
            query["role"] = role
        if status:
            query["status"] = status

        total = await db.users.count_documents(query)
        cursor = db.users.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [_doc_to_user(d) for d in docs], total

    users = list(_mem_users.values())
    if search:
        s = search.lower()
        users = [u for u in users if s in u.email.lower() or s in u.full_name.lower()]
    if role:
        users = [u for u in users if u.role.value == role]
    if status:
        users = [u for u in users if u.status.value == status]
    total = len(users)
    return users[skip:skip + limit], total


async def delete_user(user_id: str) -> None:
    db = _get_db()
    if db is not None:
        await db.users.delete_one({"_id": user_id})
    else:
        _mem_users.pop(user_id, None)



def _doc_to_user(doc: dict) -> UserRecord:
    doc["id"] = doc.pop("_id")
    return UserRecord(**doc)


# --------------------------------------------------------------------------- #
# CRUD helpers — Chat Sessions
# --------------------------------------------------------------------------- #

async def create_session(session: ChatSession) -> ChatSession:
    db = _get_db()
    if db is not None:
        doc = session.model_dump()
        doc["_id"] = doc.pop("id")
        await db.chat_sessions.insert_one(doc)
    else:
        _mem_sessions[session.id] = session
    return session


async def get_session_by_id(session_id: str) -> Optional[ChatSession]:
    db = _get_db()
    if db is not None:
        doc = await db.chat_sessions.find_one({"_id": session_id})
        if doc:
            doc["id"] = doc.pop("_id")
            return ChatSession(**doc)
        return None
    return _mem_sessions.get(session_id)


async def list_sessions(user_id: str) -> List[ChatSession]:
    db = _get_db()
    if db is not None:
        cursor = db.chat_sessions.find({"user_id": user_id, "archived": {"$ne": True}}).sort("updated_at", -1).limit(100)
        docs = await cursor.to_list(length=100)
        sessions = []
        for d in docs:
            d["id"] = d.pop("_id")
            sessions.append(ChatSession(**d))
        return sessions
    return [s for s in _mem_sessions.values() if s.user_id == user_id and not s.archived]


async def update_session(session_id: str, updates: dict) -> None:
    db = _get_db()
    updates["updated_at"] = datetime.now(timezone.utc)
    if db is not None:
        await db.chat_sessions.update_one({"_id": session_id}, {"$set": updates})
    else:
        session = _mem_sessions.get(session_id)
        if session:
            data = session.model_dump()
            data.update(updates)
            _mem_sessions[session_id] = ChatSession(**data)


async def delete_session(session_id: str) -> None:
    db = _get_db()
    if db is not None:
        await db.chat_sessions.delete_one({"_id": session_id})
    else:
        _mem_sessions.pop(session_id, None)


def _doc_to_session(doc: dict) -> ChatSession:
    doc["id"] = doc.pop("_id")
    return ChatSession(**doc)


# --------------------------------------------------------------------------- #
# CRUD helpers — Audit Logs
# --------------------------------------------------------------------------- #

async def create_audit_log(log: AuditLog) -> None:
    db = _get_db()
    doc = log.model_dump()
    doc["_id"] = doc.pop("id")
    await db.audit_logs.insert_one(doc)


async def list_audit_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[List[AuditLog], int]:
    db = _get_db()
    query: dict = {}
    if user_id:
        query["user_id"] = user_id
    if action:
        query["action"] = action
    total = await db.audit_logs.count_documents(query)
    cursor = db.audit_logs.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    logs = []
    for d in docs:
        d["id"] = d.pop("_id")
        logs.append(AuditLog(**d))
    return logs, total


# --------------------------------------------------------------------------- #
# CRUD helpers — Notifications
# --------------------------------------------------------------------------- #

async def create_notification(notif: Notification) -> None:
    db = _get_db()
    doc = notif.model_dump()
    doc["_id"] = doc.pop("id")
    await db.notifications.insert_one(doc)


async def list_notifications(user_id: str, unread_only: bool = False) -> List[Notification]:
    db = _get_db()
    query: dict = {
        "$or": [{"user_id": user_id}, {"user_id": "broadcast"}]
    }
    if unread_only:
        query["read"] = False
    cursor = db.notifications.find(query).sort("created_at", -1).limit(50)
    docs = await cursor.to_list(length=50)
    notifs = []
    for d in docs:
        d["id"] = d.pop("_id")
        notifs.append(Notification(**d))
    return notifs


async def mark_notifications_read(user_id: str) -> None:
    db = _get_db()
    await db.notifications.update_many(
        {"$or": [{"user_id": user_id}, {"user_id": "broadcast"}]},
        {"$set": {"read": True}},
    )


# --------------------------------------------------------------------------- #
# CRUD helpers — System Settings
# --------------------------------------------------------------------------- #

async def get_system_settings() -> SystemSettings:
    db = _get_db()
    doc = await db.system_settings.find_one({})
    if doc:
        doc.pop("_id", None)
        return SystemSettings(**doc)
    return SystemSettings()


async def update_system_settings(updates: dict) -> SystemSettings:
    db = _get_db()
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.system_settings.update_one({}, {"$set": updates}, upsert=True)
    return await get_system_settings()


# --------------------------------------------------------------------------- #
# Analytics helpers
# --------------------------------------------------------------------------- #

async def get_global_stats() -> Dict[str, Any]:
    """Return aggregate platform statistics for the admin dashboard."""
    db = _get_db()

    total_users = await db.users.count_documents({})
    active_users = await db.users.count_documents({"status": "active"})
    total_sessions = await db.chat_sessions.count_documents({})

    # Documents and questions from main models collection
    total_docs = await db.documents.count_documents({})
    total_questions = await db.messages.count_documents({"role": "user"})

    # Storage
    storage_pipeline = [
        {"$group": {"_id": None, "total": {"$sum": "$size_mb"}}}
    ]
    storage_result = await db.documents.aggregate(storage_pipeline).to_list(1)
    total_storage = storage_result[0]["total"] if storage_result else 0.0

    # Registrations last 7 days
    from datetime import timedelta
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    new_users_week = await db.users.count_documents({"created_at": {"$gte": week_ago}})

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_sessions": total_sessions,
        "total_documents": total_docs,
        "total_questions": total_questions,
        "total_storage_mb": round(total_storage, 2),
        "new_users_last_7_days": new_users_week,
    }


async def get_daily_activity(days: int = 30) -> List[Dict[str, Any]]:
    """Return per-day counts of messages and uploads for the past N days."""
    from datetime import timedelta
    db = _get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"created_at": {"$gte": since}, "role": "user"}},
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                    "day": {"$dayOfMonth": "$created_at"},
                },
                "questions": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    msg_docs = await db.messages.aggregate(pipeline).to_list(length=days + 5)

    upload_pipeline = [
        {"$match": {"uploaded_at": {"$gte": since}}},
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$uploaded_at"},
                    "month": {"$month": "$uploaded_at"},
                    "day": {"$dayOfMonth": "$uploaded_at"},
                },
                "uploads": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    upload_docs = await db.documents.aggregate(upload_pipeline).to_list(length=days + 5)

    # Merge into a single day-keyed dict
    day_map: dict[str, dict] = {}
    for d in msg_docs:
        key = f"{d['_id']['year']}-{d['_id']['month']:02d}-{d['_id']['day']:02d}"
        day_map.setdefault(key, {"date": key, "questions": 0, "uploads": 0})
        day_map[key]["questions"] = d["questions"]

    for d in upload_docs:
        key = f"{d['_id']['year']}-{d['_id']['month']:02d}-{d['_id']['day']:02d}"
        day_map.setdefault(key, {"date": key, "questions": 0, "uploads": 0})
        day_map[key]["uploads"] = d["uploads"]

    return sorted(day_map.values(), key=lambda x: x["date"])


async def record_audit_log(user_id: Optional[str], action: Any, detail: str, ip_address: Optional[str] = None) -> None:
    """Convenience helper to record an audit log without interrupting the calling operation."""
    try:
        if isinstance(action, str):
            try:
                action_enum = LogAction(action)
            except ValueError:
                action_enum = LogAction.LOGIN  # fallback
        else:
            action_enum = action

        log = AuditLog(user_id=user_id, action=action_enum, detail=detail, ip_address=ip_address)
        db = _get_db()
        if db is not None:
            await create_audit_log(log)
        else:
            _mem_logs.append(log)
    except Exception as exc:
        logger.warning("Failed to record audit log (non-fatal): %s", exc)


async def get_audit_logs(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[List[AuditLog], int]:
    """Convenience helper to retrieve audit logs with pagination."""
    db = _get_db()
    if db is not None:
        return await list_audit_logs(user_id=user_id, action=action, skip=skip, limit=limit)
    else:
        filtered = [
            l for l in _mem_logs
            if (user_id is None or l.user_id == user_id) and (action is None or l.action == action)
        ]
        return filtered[skip : skip + limit], len(filtered)


async def get_notifications(user_id: str) -> List[Notification]:
    """Convenience helper to retrieve notifications."""
    db = _get_db()
    if db is not None:
        return await list_notifications(user_id=user_id)
    else:
        return [n for n in _mem_notifications if n.user_id == user_id or n.user_id == "broadcast"]

