"""
backend/inspect_data.py
CLI inspection utility for SS SPARK database and RAG vector store.

Usage:
  python backend/inspect_data.py
  python backend/inspect_data.py --users
  python backend/inspect_data.py --docs
  python backend/inspect_data.py --rag
  python backend/inspect_data.py --chats
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.config import get_settings
from database.models import init_db
from database.user_models import list_users
from rag.vector_store import get_vector_store


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def show_users(db):
    print("\n" + "="*60)
    print(" [1] MONGODB USERS")
    print("="*60)
    try:
        users, total = await list_users(limit=100)
        if not users:
            print("  No users registered yet.")
            return

        print(f"  Total Registered Users: {total}\n")
        print(f"  {'EMAIL':<30} {'ROLE':<10} {'DOCS':<6} {'QUESTIONS':<10} {'STATUS':<10}")
        print("  " + "-"*68)
        for u in users:
            print(f"  {u.email:<30} {u.role.value:<10} {u.total_documents:<6} {u.total_questions:<10} {u.status.value:<10}")
    except Exception as e:
        print(f"  Error reading users: {e}")


async def show_documents(db):
    print("\n" + "="*60)
    print(" [2] MONGODB UPLOADED DOCUMENTS")
    print("="*60)
    try:
        if db is not None:
            cursor = db.documents.find({}).sort("uploaded_at", -1).limit(50)
            docs = await cursor.to_list(length=50)
        else:
            from database.models import _mem_docs
            docs = [d.model_dump() for d in _mem_docs.values()]

        if not docs:
            print("  No documents uploaded yet.")
            return

        print(f"  {'FILENAME':<35} {'KIND':<8} {'PAGES':<6} {'CHUNKS':<8} {'QUESTIONS':<10}")
        print("  " + "-"*70)
        for d in docs:
            fname = str(d.get("name") or d.get("filename") or "Unknown")[:34]
            kind = str(d.get("kind", "pdf"))[:7]
            pages = str(d.get("pages", 1))
            chunks = str(d.get("chunk_count", 0))
            q_cnt = str(d.get("questions_count", 0))
            print(f"  {fname:<35} {kind:<8} {pages:<6} {chunks:<8} {q_cnt:<10}")
    except Exception as e:
        print(f"  Error reading documents: {e}")


async def show_chats(db):
    print("\n" + "="*60)
    print(" [3] MONGODB CHAT SESSIONS & MESSAGES")
    print("="*60)
    try:
        if db is not None:
            sessions = await db.chat_sessions.find({}).sort("updated_at", -1).limit(10).to_list(10)
            msg_count = await db.chat_messages.count_documents({})
        else:
            from database.models import _mem_sessions, _mem_messages
            sessions = [s.model_dump() for s in _mem_sessions.values()]
            msg_count = len(_mem_messages)

        print(f"  Total Messages Persisted: {msg_count}")
        print(f"  Recent Sessions: {len(sessions)}\n")
        for s in sessions:
            title = str(s.get("title", "New Chat"))[:40]
            msgs = s.get("message_count", 0)
            user_id = str(s.get("user_id", "anon"))[:12]
            print(f"  - [{user_id}] {title} ({msgs} msgs)")
    except Exception as e:
        print(f"  Error reading chat data: {e}")


def show_rag():
    print("\n" + "="*60)
    print(" [4] RAG VECTOR STORE (ChromaDB / Qdrant)")
    print("="*60)
    try:
        cfg = get_settings()
        vs = get_vector_store(str(cfg.CHROMA_DIR), cfg.CHROMA_COLLECTION)
        total_chunks = vs.count()
        print(f"  Storage Location : {cfg.CHROMA_DIR}")
        print(f"  Collection Name  : {cfg.CHROMA_COLLECTION}")
        print(f"  Total Chunks     : {total_chunks}")

        if total_chunks > 0:
            print("\n  Sample Indexed Vector Chunks:")
            # Query a sample
            from rag.embeddings import get_embedder
            emb = get_embedder().embed(["examination question math"])[0]
            results = vs.search(emb, n_results=min(3, total_chunks))
            for idx, r in enumerate(results, 1):
                src = r.get("source", "N/A")
                pg = r.get("page", 1)
                q_num = r.get("question_number", "-")
                txt = r.get("text", "")[:120].replace("\n", " ")
                print(f"    [{idx}] Source: {src} (Page {pg}, Question: {q_num})")
                print(f"        Snippet: {txt}...")
    except Exception as e:
        print(f"  Error reading RAG vector store: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Inspect MongoDB and RAG data for SS SPARK.")
    parser.add_argument("--users", action="store_true", help="Show users collection")
    parser.add_argument("--docs", action="store_true", help="Show documents collection")
    parser.add_argument("--chats", action="store_true", help="Show chats collection")
    parser.add_argument("--rag", action="store_true", help="Show RAG vector store data")
    args = parser.parse_args()

    show_all = not (args.users or args.docs or args.chats or args.rag)

    cfg = get_settings()
    from database.models import _db
    await init_db(cfg.MONGO_URI, cfg.MONGO_DB_NAME)
    from database.models import _db as connected_db

    print("\n" + "#"*60)
    print(f" SS SPARK DATA INSPECTOR | MongoDB: {cfg.MONGO_DB_NAME}")
    print("#"*60)

    if show_all or args.users:
        await show_users(connected_db)
    if show_all or args.docs:
        await show_documents(connected_db)
    if show_all or args.chats:
        await show_chats(connected_db)
    if show_all or args.rag:
        show_rag()

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
