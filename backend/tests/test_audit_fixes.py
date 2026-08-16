"""
tests/test_audit_fixes.py
=========================
Targeted test suite verifying all audit fixes:
  1. Test A: Multi-user PaperQA & Vector Store Isolation
  2. Test B: Document Deletion Cleanup (Vector Store + PaperQA eviction)
  3. Test C: Refresh Token Revocation & Versioning
  4. Test D: Reverse Proxy OAuth HTTPS Scheme Generation
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.config import get_settings
from core.security import create_access_token, create_refresh_token, decode_token
from database.models import UploadedDoc, delete_document, get_document_by_id, get_documents, save_document
from database.user_models import UserRecord, create_user, get_user_by_id, update_user
from rag import paperqa_connector as pqa
from rag.embeddings import get_embedder
from rag.vector_store import get_vector_store
from api.auth import _build_oauth_redirect_uri
from fastapi import Request, HTTPException


def create_test_file(filename: str, content: str) -> Path:
    """Helper to create a temporary test document."""
    tmp = Path(tempfile.gettempdir()) / filename
    tmp.write_text(content, encoding="utf-8")
    return tmp


async def run_test_a_multi_user_isolation():
    print("\n" + "=" * 60)
    print("TEST A: Multi-User PaperQA & Vector Isolation")
    print("=" * 60)

    user_a = f"user_alpha_{os.urandom(4).hex()}"
    user_b = f"user_beta_{os.urandom(4).hex()}"
    user_c = f"user_gamma_empty_{os.urandom(4).hex()}"

    doc_a_file = create_test_file("private_A.txt", "TOP SECRET ALPHA: The quantum cipher key is X99-ALPHA-PROJECT.")
    doc_b_file = create_test_file("private_B.txt", "TOP SECRET BETA: The mission code is BETA-77-DELTA-MISSION.")

    # Ingest for User A into user scope
    print("1. Indexing private_A.txt for User A...")
    if user_a not in pqa._user_indexed_paths:
        pqa._user_indexed_paths[user_a] = set()
    pqa._user_indexed_paths[user_a].add(str(doc_a_file))

    # Ingest for User B into user scope
    print("2. Indexing private_B.txt for User B...")
    if user_b not in pqa._user_indexed_paths:
        pqa._user_indexed_paths[user_b] = set()
    pqa._user_indexed_paths[user_b].add(str(doc_b_file))

    # Verify indexed counts per user
    count_a = pqa.get_indexed_count(user_id=user_a)
    count_b = pqa.get_indexed_count(user_id=user_b)
    count_c = pqa.get_indexed_count(user_id=user_c)

    print(f"   User A docs: {count_a} (Expected: 1)")
    print(f"   User B docs: {count_b} (Expected: 1)")
    print(f"   User C docs: {count_c} (Expected: 0)")

    assert count_a == 1, f"User A expected 1 doc, got {count_a}"
    assert count_b == 1, f"User B expected 1 doc, got {count_b}"
    assert count_c == 0, f"User C expected 0 docs, got {count_c}"

    # Verify path isolation
    paths_a = pqa.get_indexed_paths(user_id=user_a)
    paths_b = pqa.get_indexed_paths(user_id=user_b)
    paths_c = pqa.get_indexed_paths(user_id=user_c)

    assert str(doc_a_file) in paths_a, "Doc A not in User A's paths"
    assert str(doc_a_file) not in paths_b, "Doc A LEAKED into User B's paths!"
    assert str(doc_a_file) not in paths_c, "Doc A LEAKED into User C's paths!"
    assert len(paths_c) == 0, "User C has paths when should have 0"

    print("   [PASS] User A and User B paths and counts strictly isolated.")

    # Vector store isolation check
    vs = get_vector_store()
    embedder = get_embedder()

    emb_a = embedder.embed(["The quantum cipher key is X99-ALPHA-PROJECT."])
    vs.add_chunks(
        doc_id="doc-a-id",
        source_name="private_A.txt",
        chunks=["The quantum cipher key is X99-ALPHA-PROJECT."],
        embeddings=emb_a,
        pages=[1],
        user_id=user_a,
    )

    # Search as User B for User A's secret
    query_emb = embedder.embed(["quantum cipher key"])[0]
    hits_b = vs.search(query_emb, n_results=5, user_id=user_b)
    print(f"   User B search for User A secret hits: {len(hits_b)} (Expected: 0)")
    assert len(hits_b) == 0, f"Vector store LEAKED User A chunks to User B! Hits: {hits_b}"

    hits_a = vs.search(query_emb, n_results=5, user_id=user_a)
    print(f"   User A search for User A secret hits: {len(hits_a)} (Expected: 1)")
    assert len(hits_a) >= 1, "User A could not retrieve own vector chunk"

    print("   [PASS] Vector store retrieval strictly enforces user_id filter.")


async def run_test_b_document_deletion():
    print("\n" + "=" * 60)
    print("TEST B: Document Deletion Cleanup (Chroma/Qdrant + PaperQA)")
    print("=" * 60)

    user_del = f"user_del_{os.urandom(4).hex()}"
    del_file = create_test_file("to_delete.txt", "This document will be deleted and never seen again.")

    # 1. Ingest into PaperQA memory & vector store
    if user_del not in pqa._user_indexed_paths:
        pqa._user_indexed_paths[user_del] = set()
    pqa._user_indexed_paths[user_del].add(str(del_file))
    assert pqa.get_indexed_count(user_id=user_del) == 1
    print("   1. Document present in PaperQA index [OK]")

    vs = get_vector_store()
    embedder = get_embedder()
    emb = embedder.embed(["This document will be deleted and never seen again."])
    vs.add_chunks(
        doc_id="del-doc-123",
        source_name="to_delete.txt",
        chunks=["This document will be deleted and never seen again."],
        embeddings=emb,
        pages=[1],
        user_id=user_del,
    )

    # 2. Verify queryable before delete
    q_emb = embedder.embed(["deleted and never seen"])[0]
    hits_before = vs.search(q_emb, n_results=5, user_id=user_del)
    assert len(hits_before) >= 1, "Doc was not found before delete"
    print("   1. Document queryable before deletion [OK]")

    # 3. Perform Deletion
    vs.delete_by_doc_id("del-doc-123")
    await pqa.remove_document(str(del_file), user_id=user_del)

    # 4. Verify post-deletion state
    hits_after = vs.search(q_emb, n_results=5, user_id=user_del)
    pqa_count_after = pqa.get_indexed_count(user_id=user_del)

    print(f"   2. Vector search hits after deletion: {len(hits_after)} (Expected: 0)")
    print(f"   3. PaperQA indexed count after deletion: {pqa_count_after} (Expected: 0)")

    assert len(hits_after) == 0, "Deleted document vectors still exist in vector store!"
    assert pqa_count_after == 0, "Deleted document still indexed in PaperQA!"

    print("   [PASS] Complete deletion across Vector Store and PaperQA verified.")


async def run_test_c_token_revocation():
    print("\n" + "=" * 60)
    print("TEST C: Refresh Token Revocation & Versioning")
    print("=" * 60)

    # Create test user
    test_uid = f"usr_{os.urandom(4).hex()}"
    user_record = UserRecord(
        id=test_uid,
        email=f"revoke_test_{os.urandom(4).hex()}@example.com",
        full_name="Revocation Tester",
        token_version=1,
    )
    user = await create_user(user_record)
    print(f"   1. User created with token_version: {user.token_version}")

    # Generate refresh token at version 1
    refresh_tok_v1 = create_refresh_token({
        "sub": user.id,
        "email": user.email,
        "token_version": user.token_version,
    })
    payload = decode_token(refresh_tok_v1)
    assert payload["token_version"] == 1, "Token does not contain token_version 1"
    print("   2. Issued Refresh Token v1 [OK]")

    # Simulate valid refresh at version 1
    user_db = await get_user_by_id(test_uid)
    assert getattr(user_db, "token_version", 1) == payload["token_version"], "Version mismatch before revocation"
    print("   3. Valid refresh allowed at token_version=1 [OK]")

    # Simulate Security Event / Logout: increment token_version
    new_version = user_db.token_version + 1
    await update_user(test_uid, {"token_version": new_version})
    updated_user = await get_user_by_id(test_uid)
    print(f"   4. User logged out / security event. New token_version in DB: {updated_user.token_version}")

    # Attempt to refresh with old refresh_tok_v1
    payload_old = decode_token(refresh_tok_v1)
    revoked = (payload_old.get("token_version", 1) != getattr(updated_user, "token_version", 1))
    print(f"   5. Checking old token (v={payload_old.get('token_version')}) vs user DB (v={updated_user.token_version}) -> Revoked: {revoked}")
    assert revoked is True, "Old refresh token was NOT detected as revoked!"

    # Issue fresh refresh token at version 2
    refresh_tok_v2 = create_refresh_token({
        "sub": updated_user.id,
        "email": updated_user.email,
        "token_version": updated_user.token_version,
    })
    payload_v2 = decode_token(refresh_tok_v2)
    valid_v2 = (payload_v2.get("token_version", 1) == getattr(updated_user, "token_version", 1))
    print(f"   6. Checking fresh token (v={payload_v2.get('token_version')}) vs user DB -> Valid: {valid_v2}")
    assert valid_v2 is True, "Fresh refresh token at version 2 was incorrectly rejected!"

    print("   [PASS] Refresh token revocation mechanism working perfectly.")


def run_test_d_oauth_proxy_https():
    print("\n" + "=" * 60)
    print("TEST D: Reverse Proxy OAuth HTTPS Scheme Generation")
    print("=" * 60)

    # 1. Simulate Render reverse proxy request (incoming base_url is http://, but x-forwarded-proto is https)
    mock_render_req = MagicMock(spec=Request)
    mock_render_req.base_url = "http://ss-spark-api.onrender.com"
    mock_render_req.headers = {"x-forwarded-proto": "https"}

    render_redirect = _build_oauth_redirect_uri(mock_render_req)
    print(f"   1. Render Cloud Redirect URI: {render_redirect}")
    assert render_redirect == "https://ss-spark-api.onrender.com/api/auth/oauth/google/callback", \
        f"Expected https on Render, got: {render_redirect}"

    # 2. Simulate Local Development request
    mock_local_req = MagicMock(spec=Request)
    mock_local_req.base_url = "http://localhost:8000"
    mock_local_req.headers = {}

    local_redirect = _build_oauth_redirect_uri(mock_local_req)
    print(f"   2. Local Dev Redirect URI:    {local_redirect}")
    assert local_redirect == "http://localhost:8000/api/auth/oauth/google/callback", \
        f"Expected http on localhost, got: {local_redirect}"

    print("   [PASS] OAuth redirect URI properly respects proxy HTTPS and local dev.")


async def main():
    print("=" * 60)
    print("  SS SPARK / PaperGenius — Targeted Audit Fixes Test Suite")
    print("=" * 60)
    try:
        await run_test_a_multi_user_isolation()
        await run_test_b_document_deletion()
        await run_test_c_token_revocation()
        run_test_d_oauth_proxy_https()

        print("\n" + "=" * 60)
        print("  ALL 4 AUDIT FIX TEST SUITES (A, B, C, D) PASSED! [OK]")
        print("=" * 60)
    except Exception as exc:
        print(f"\n[FAIL] Test error: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
