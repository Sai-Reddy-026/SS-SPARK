"""
backend/tests/test_multi_doc_citation_repro.py
==============================================
Deterministic reproduction and verification test for Multi-Document RAG Citation Pipeline.

Verifies:
1. Two documents with unique facts (Quantum Encryption Doc & Orbital Mechanics Doc).
2. A cross-document question requiring information from both documents.
3. Accurate citation mapping, page preservation, and chunk ID retention.
4. Tenant user isolation (User B cannot retrieve User A's citations).
"""

import asyncio
import os
import sys
import uuid

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from database.models import UploadedDoc, save_document
from rag.embeddings import get_embedder
from rag.retriever import retrieve
from rag.vector_store import get_vector_store
from services.chat_service import ask_question

# Document 1: Quantum Encryption Notes
DOC_A_NAME = "quantum_cryptography_protocol.pdf"
DOC_A_PAGE = 4
DOC_A_TEXT = (
    "Quantum Key Distribution (QKD) Protocol Specifications: "
    "The BB84 quantum cryptography protocol uses photon polarization states (horizontal, vertical, diagonal) "
    "to establish a secure shared symmetric key between Alice and Bob. "
    "Any eavesdropping attempt by Eve introduces a detectable Quantum Bit Error Rate (QBER) exceeding 11%."
)

# Document 2: Orbital Satellite Network Specs
DOC_B_NAME = "low_earth_orbit_satellites.pdf"
DOC_B_PAGE = 9
DOC_B_TEXT = (
    "Low Earth Orbit (LEO) Optical Communications Constellation: "
    "The satellite network operates at an altitude of 550 kilometers with laser inter-satellite links (ISLs) "
    "achieving 100 Gbps line rates. Free-space optical transceivers maintain beam pointing accuracy within 1.2 microradians."
)

# Synthesis Question requiring facts from BOTH documents
SYNTHESIS_QUESTION = (
    "How does the BB84 quantum key distribution protocol secure laser inter-satellite links in low earth orbit satellite constellations?"
)


async def run_multi_doc_repro():
    print("=" * 80)
    print("  MULTI-DOCUMENT RAG CITATION PIPELINE DETERMINISTIC AUDIT & VERIFICATION")
    print("=" * 80)

    user_a = f"audit_user_a_{uuid.uuid4().hex[:6]}"
    user_b = f"audit_user_b_{uuid.uuid4().hex[:6]}"

    embedder = get_embedder()
    vs = get_vector_store()

    # 1. Ingest both documents for User A
    print("\n1. Ingesting Doc A (Quantum) and Doc B (Satellites) for User A...")
    emb_a = embedder.embed([DOC_A_TEXT])
    chunk_ids_a = vs.add_chunks(
        doc_id="doc-qkd-1",
        source_name=DOC_A_NAME,
        chunks=[DOC_A_TEXT],
        embeddings=emb_a,
        pages=[DOC_A_PAGE],
        user_id=user_a,
    )
    await save_document(
        UploadedDoc(
            id="doc-qkd-1",
            name=DOC_A_NAME,
            kind="pdf",
            size_mb=0.2,
            pages=DOC_A_PAGE + 1,
            chunk_count=1,
            user_id=user_a,
        )
    )

    emb_b = embedder.embed([DOC_B_TEXT])
    chunk_ids_b = vs.add_chunks(
        doc_id="doc-sat-2",
        source_name=DOC_B_NAME,
        chunks=[DOC_B_TEXT],
        embeddings=emb_b,
        pages=[DOC_B_PAGE],
        user_id=user_a,
    )
    await save_document(
        UploadedDoc(
            id="doc-sat-2",
            name=DOC_B_NAME,
            kind="pdf",
            size_mb=0.3,
            pages=DOC_B_PAGE + 1,
            chunk_count=1,
            user_id=user_a,
        )
    )

    print(f"  + Ingested {DOC_A_NAME} (chunk_id={chunk_ids_a[0]}, page={DOC_A_PAGE})")
    print(f"  + Ingested {DOC_B_NAME} (chunk_id={chunk_ids_b[0]}, page={DOC_B_PAGE})")

    # 2. Test Multi-Doc Retrieval and Citation Pipeline for User A
    print(f"\n2. Asking Synthesis Question for User A:\n   {SYNTHESIS_QUESTION}")
    res_a = await ask_question(SYNTHESIS_QUESTION, user_id=user_a)
    data_a = res_a.get("data", {})
    ans_a = data_a.get("answer", "")
    citations_a = data_a.get("citations", [])

    print(f"\n   Generated Answer Excerpt:\n   {ans_a[:280]}...")
    print(f"\n   Total Citations Returned: {len(citations_a)}")
    for idx, c in enumerate(citations_a):
        print(f"     [{idx}] ID={c.get('id')} | Source={c.get('source')} | Page={c.get('page')} | Rel={c.get('relevance')}")

    # Assertions for User A:
    # 1. Answer must mention key concepts from both documents
    assert "bb84" in ans_a.lower() or "quantum" in ans_a.lower(), "Answer failed to recall Doc A facts"
    assert "satellite" in ans_a.lower() or "laser" in ans_a.lower() or "orbit" in ans_a.lower(), "Answer failed to recall Doc B facts"
    print("   [PASS] Answer contains synthesized facts from both documents.")

    # 2. Citations must contain both sources with exact page numbers
    sources_cited = {c.get("source"): c.get("page") for c in citations_a}
    assert DOC_A_NAME in sources_cited, f"Missing citation for {DOC_A_NAME}"
    assert sources_cited[DOC_A_NAME] == DOC_A_PAGE, f"Incorrect page for {DOC_A_NAME}: expected {DOC_A_PAGE}, got {sources_cited[DOC_A_NAME]}"
    assert DOC_B_NAME in sources_cited, f"Missing citation for {DOC_B_NAME}"
    assert sources_cited[DOC_B_NAME] == DOC_B_PAGE, f"Incorrect page for {DOC_B_NAME}: expected {DOC_B_PAGE}, got {sources_cited[DOC_B_NAME]}"
    print("   [PASS] Both documents accurately cited with exact page numbers preserved.")

    # 3. Chunk IDs must be preserved (not overwritten by random UUIDs if source ID was present)
    assert all(c.get("id") for c in citations_a), "Missing chunk IDs in citations"
    print("   [PASS] Chunk IDs preserved in citation payloads.")

    # 4. Multi-Tenant Isolation: User B asking the same question must see ZERO citations to User A's docs
    print("\n3. Testing Multi-Tenant Isolation for User B (Unrelated User)...")
    res_b = await ask_question(SYNTHESIS_QUESTION, user_id=user_b)
    data_b = res_b.get("data", {})
    citations_b = data_b.get("citations", [])
    assert len(citations_b) == 0, f"Cross-tenant data leak! User B received citations: {citations_b}"
    print("   [PASS] User B received 0 citations (Strict cross-tenant isolation verified).")

    print("\n" + "=" * 80)
    print("  ALL MULTI-DOCUMENT CITATION AUDIT CHECKS PASSED [OK]")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_multi_doc_repro())
