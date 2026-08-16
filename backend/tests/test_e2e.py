"""
backend/test_e2e.py
===================
End-to-end verification script for SS SPARK.

Run from the backend/ directory:
    cd backend
    python test_e2e.py

Tests:
  1. Dependency check
  2. MongoDB connectivity
  3. ChromaDB vector store
  4. Local embedding (sentence-transformers)
  5. PDF text extraction
  6. Full upload pipeline (extract → chunk → embed → store)
  7. Vector store retrieval
  8. PaperQA indexing (without LLM call)
  9. API key / LLM availability check
  10. Backend startup config check
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import traceback
from pathlib import Path

# Ensure backend package is importable
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

results: list[tuple[str, str, str]] = []


def record(status: str, test: str, detail: str = "") -> None:
    results.append((status, test, detail))
    symbol = {"[PASS]": "OK ", "[FAIL]": "ERR", "[WARN]": "WRN", "[INFO]": "INF"}[status]
    print(f"  [{symbol}] {test}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# 1. Core dependencies
# ---------------------------------------------------------------------------

def test_deps() -> None:
    print("\n=== 1. Core Dependencies ===")

    for pkg, label in [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("motor.motor_asyncio", "Motor (MongoDB async driver)"),
        ("pymongo", "PyMongo"),
        ("jose", "python-jose (JWT)"),
        ("bcrypt", "bcrypt"),
        ("pydantic_settings", "pydantic-settings"),
        ("fitz", "PyMuPDF"),
        ("chromadb", "ChromaDB"),
        ("qdrant_client", "qdrant-client"),
        ("paperqa", "PaperQA"),
        ("litellm", "LiteLLM"),
    ]:
        try:
            __import__(pkg)
            record(PASS, label)
        except ImportError as e:
            record(FAIL, label, str(e))

    # sentence-transformers (local embeddings fallback)
    try:
        import sentence_transformers  # noqa: F401
        record(PASS, "sentence-transformers (local embedder)")
    except ImportError:
        record(FAIL, "sentence-transformers (local embedder)",
               "Run: pip install sentence-transformers")

    # python-docx
    try:
        import docx  # noqa: F401
        record(PASS, "python-docx")
    except ImportError:
        record(WARN, "python-docx", "DOCX uploads will fail — run: pip install python-docx")


# ---------------------------------------------------------------------------
# 2. MongoDB
# ---------------------------------------------------------------------------

async def test_mongodb() -> None:
    print("\n=== 2. MongoDB Connectivity ===")
    try:
        import motor.motor_asyncio as motor
        from core.config import get_settings
        cfg = get_settings()

        client = motor.AsyncIOMotorClient(cfg.MONGO_URI, serverSelectionTimeoutMS=3000)
        await client.admin.command("ping")
        record(PASS, "MongoDB ping", cfg.MONGO_URI)
        client.close()
    except Exception as e:
        record(FAIL, "MongoDB ping", str(e))


# ---------------------------------------------------------------------------
# 3. Local embedder (sentence-transformers)
# ---------------------------------------------------------------------------

def test_local_embedder() -> None:
    print("\n=== 3. Local Embedding (sentence-transformers) ===")
    try:
        # Force local embedder by clearing API keys temporarily
        orig_openai = os.environ.pop("OPENAI_API_KEY", "")
        orig_gemini = os.environ.pop("GEMINI_API_KEY", "")

        # Reset singleton
        from rag import embeddings as emb_module
        emb_module._embedder_instance = None

        embedder = emb_module.get_embedder()
        vectors = embedder.embed(["What is a question paper?", "Explain the syllabus."])
        assert len(vectors) == 2
        dim = len(vectors[0])
        record(PASS, "Local embedder", f"dim={dim}, model=all-MiniLM-L6-v2")

        # Restore
        if orig_openai:
            os.environ["OPENAI_API_KEY"] = orig_openai
        if orig_gemini:
            os.environ["GEMINI_API_KEY"] = orig_gemini
        emb_module._embedder_instance = None  # reset so next caller picks real key

    except Exception as e:
        record(FAIL, "Local embedder", str(e))


# ---------------------------------------------------------------------------
# 4. ChromaDB
# ---------------------------------------------------------------------------

def test_chromadb() -> None:
    print("\n=== 4. ChromaDB Vector Store ===")
    try:
        from core.config import get_settings
        from rag.vector_store import VectorStore

        cfg = get_settings()
        vs = VectorStore(str(cfg.CHROMA_DIR), cfg.CHROMA_COLLECTION)
        count = vs.count()
        record(PASS, "ChromaDB init", f"collection={cfg.CHROMA_COLLECTION}, vectors={count}")
    except Exception as e:
        record(FAIL, "ChromaDB init", str(e))


# ---------------------------------------------------------------------------
# 5. PDF extraction
# ---------------------------------------------------------------------------

def test_pdf_extraction() -> None:
    print("\n=== 5. PDF / Text Extraction ===")

    # Create a minimal test PDF using PyMuPDF
    try:
        import fitz  # PyMuPDF

        tmp = Path(tempfile.gettempdir()) / "ss_spark_test_paper.pdf"
        doc = fitz.open()  # new empty PDF
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            (
                "SS SPARK Test Question Paper\n\n"
                "Q1. What is the capital of France?\n"
                "Answer: The capital of France is Paris.\n\n"
                "Q2. What is photosynthesis?\n"
                "Answer: Photosynthesis is the process by which plants use sunlight, "
                "water, and carbon dioxide to produce food and oxygen.\n\n"
                "Q3. State Newton's Second Law of Motion.\n"
                "Answer: Force equals mass times acceleration (F = ma).\n"
            ),
            fontsize=12,
        )
        doc.save(str(tmp))
        doc.close()
        record(PASS, "Test PDF created", str(tmp))

        # Extract chunks
        from services.pdf_service import extract_chunks, count_pdf_pages
        chunks = extract_chunks(str(tmp), doc_id="test-doc-001", chunk_size=100, overlap=10)
        pages = count_pdf_pages(str(tmp))
        record(PASS, "PDF text extraction", f"chunks={len(chunks)}, pages={pages}")

        # Store test PDF path in a module-level variable for later phases
        global _TEST_PDF_PATH
        _TEST_PDF_PATH = str(tmp)

    except Exception as e:
        record(FAIL, "PDF extraction", str(e))
        traceback.print_exc()

_TEST_PDF_PATH: str = ""


# ---------------------------------------------------------------------------
# 6. Full upload pipeline (no HTTP — direct service calls)
# ---------------------------------------------------------------------------

async def test_upload_pipeline() -> None:
    print("\n=== 6. Full Upload Pipeline (extract->chunk->embed->store) ===")

    global _TEST_PDF_PATH
    if not _TEST_PDF_PATH or not Path(_TEST_PDF_PATH).exists():
        record(WARN, "Upload pipeline", "Skipped — test PDF not created in Phase 5")
        return

    try:
        from core.config import get_settings
        from services.pdf_service import extract_chunks
        from rag.embeddings import get_embedder
        from rag.vector_store import VectorStore

        cfg = get_settings()
        doc_id = "test-doc-001"

        # Extract
        chunks = extract_chunks(_TEST_PDF_PATH, doc_id=doc_id,
                                chunk_size=100, overlap=10)
        assert chunks, "No chunks extracted!"
        record(PASS, "Text chunking", f"{len(chunks)} chunks from test PDF")

        # Embed (uses local sentence-transformers)
        from rag import embeddings as emb_module
        emb_module._embedder_instance = None  # ensure fresh instance
        embedder = get_embedder()
        texts = [c.text for c in chunks]
        pages = [c.page for c in chunks]
        embeddings = embedder.embed(texts)
        record(PASS, "Embedding generation",
               f"{len(embeddings)} embeddings, dim={len(embeddings[0])}")

        # Store in ChromaDB
        vs = VectorStore(str(cfg.CHROMA_DIR), cfg.CHROMA_COLLECTION)
        # Delete any old test chunks first
        vs.delete_by_doc_id(doc_id)

        chunk_ids = vs.add_chunks(
            doc_id=doc_id,
            source_name="pg_test_paper.pdf",
            chunks=texts,
            embeddings=embeddings,
            pages=pages,
            user_id="test-user-001",
        )
        record(PASS, "ChromaDB storage",
               f"{len(chunk_ids)} chunk IDs stored for doc_id={doc_id}")

    except Exception as e:
        record(FAIL, "Upload pipeline", str(e))
        traceback.print_exc()


# ---------------------------------------------------------------------------
# 7. Vector retrieval
# ---------------------------------------------------------------------------

def test_retrieval() -> None:
    print("\n=== 7. Vector Store Retrieval ===")
    try:
        from core.config import get_settings
        from rag.vector_store import VectorStore
        from rag.embeddings import get_embedder

        cfg = get_settings()
        vs = VectorStore(str(cfg.CHROMA_DIR), cfg.CHROMA_COLLECTION)

        if vs.count() == 0:
            record(WARN, "Retrieval", "ChromaDB is empty — upload pipeline may have failed")
            return

        embedder = get_embedder()
        query = "What is the capital of France?"
        q_emb = embedder.embed([query])[0]

        hits = vs.search(q_emb, n_results=3, user_id="test-user-001")
        record(PASS, "Vector search", f"{len(hits)} hits for '{query}'")

        for i, h in enumerate(hits[:2], 1):
            record(INFO, f"  Hit {i}",
                   f"source={h['source']}, page={h['page']}, "
                   f"relevance={h['relevance']}, snippet={h['text'][:80]!r}")

        # Negative test — unrelated question
        q_unrelated = "Explain quantum entanglement in dark matter"
        q_emb2 = embedder.embed([q_unrelated])[0]
        hits2 = vs.search(q_emb2, n_results=3, user_id="test-user-001")
        if hits2:
            top_rel = hits2[0]["relevance"]
            if top_rel < 0.5:
                record(PASS, "Low-relevance guard",
                       f"Unrelated query: top relevance={top_rel:.3f} (< 0.5 — correct)")
            else:
                record(WARN, "Low-relevance guard",
                       f"Unrelated query: top relevance={top_rel:.3f} (>= 0.5 — may hallucinate)")

    except Exception as e:
        record(FAIL, "Retrieval", str(e))
        traceback.print_exc()


# ---------------------------------------------------------------------------
# 8. PaperQA indexing (without LLM call)
# ---------------------------------------------------------------------------

async def test_paperqa_indexing() -> None:
    print("\n=== 8. PaperQA Indexing (no LLM call) ===")

    global _TEST_PDF_PATH
    if not _TEST_PDF_PATH or not Path(_TEST_PDF_PATH).exists():
        record(WARN, "PaperQA indexing", "Skipped — test PDF not created")
        return

    try:
        from rag.paperqa_connector import _get_or_create_docs, get_indexed_count

        docs = _get_or_create_docs()
        record(PASS, "PaperQA Docs instance", f"type={type(docs).__name__}")
        record(INFO, "PaperQA indexed docs",
               f"{get_indexed_count()} (aadd() not called — requires LLM API for citation)")
    except Exception as e:
        record(FAIL, "PaperQA Docs instance", str(e))


# ---------------------------------------------------------------------------
# 9. LLM / API key check
# ---------------------------------------------------------------------------

def test_llm_config() -> None:
    print("\n=== 9. LLM & API Key Configuration ===")
    from core.config import get_settings
    cfg = get_settings()

    record(INFO, "OPENAI_API_KEY", "SET" if cfg.OPENAI_API_KEY else "NOT SET")
    record(INFO, "GEMINI_API_KEY", "SET" if cfg.GEMINI_API_KEY else "NOT SET")
    record(INFO, "ANTHROPIC_API_KEY", "SET" if cfg.ANTHROPIC_API_KEY else "NOT SET")

    if cfg.has_any_llm_key:
        record(WARN, "LLM key present",
               "Key is SET but internet connectivity is required for cloud LLMs. "
               "If the shell has no internet, PaperQA agent_query() calls will fail. "
               "Install Ollama for a fully offline LLM.")
    else:
        record(FAIL, "LLM configuration",
               "No LLM API key set. Set OPENAI_API_KEY, GEMINI_API_KEY, or "
               "ANTHROPIC_API_KEY in backend/.env — OR install Ollama for offline use.")

    record(INFO, "USE_QDRANT", str(cfg.USE_QDRANT))
    record(INFO, "CHROMA_DIR", str(cfg.CHROMA_DIR))
    record(INFO, "UPLOAD_DIR", str(cfg.UPLOAD_DIR))
    record(INFO, "FRONTEND_URL / CORS", str(cfg.FRONTEND_URL))
    record(INFO, "ALLOWED_ORIGINS", str(cfg.ALLOWED_ORIGINS))


# ---------------------------------------------------------------------------
# 10. Backend config integrity
# ---------------------------------------------------------------------------

def test_backend_config() -> None:
    print("\n=== 10. Backend Config Integrity ===")
    from core.config import get_settings
    cfg = get_settings()

    # Upload dir exists
    if cfg.UPLOAD_DIR.exists():
        record(PASS, "Upload directory exists", str(cfg.UPLOAD_DIR))
    else:
        record(WARN, "Upload directory", f"Missing — will be auto-created: {cfg.UPLOAD_DIR}")

    # ChromaDB dir exists
    if cfg.CHROMA_DIR.exists():
        record(PASS, "ChromaDB directory exists", str(cfg.CHROMA_DIR))
    else:
        record(WARN, "ChromaDB directory", f"Missing — will be auto-created: {cfg.CHROMA_DIR}")

    # JWT secret strength
    secret = cfg.JWT_SECRET_KEY
    if len(secret) >= 32 and "changeme" not in secret.lower():
        record(PASS, "JWT_SECRET_KEY strength", f"length={len(secret)}")
    else:
        record(WARN, "JWT_SECRET_KEY",
               "Too short or still default — change before deploying to production")

    # CORS includes frontend port
    origins = cfg.ALLOWED_ORIGINS
    if any("8080" in o or "5173" in o for o in origins):
        record(PASS, "CORS origins include frontend ports", str(origins))
    else:
        record(WARN, "CORS", f"Frontend port not in ALLOWED_ORIGINS: {origins}")

    # MongoDB URI
    record(INFO, "MONGO_URI", cfg.MONGO_URI)
    record(INFO, "MONGO_DB_NAME", cfg.MONGO_DB_NAME)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def main() -> None:
    print("=" * 60)
    print("  SS SPARK — End-to-End Verification Script")
    print("=" * 60)

    test_deps()
    await test_mongodb()
    test_local_embedder()
    test_chromadb()
    test_pdf_extraction()
    await test_upload_pipeline()
    test_retrieval()
    await test_paperqa_indexing()
    test_llm_config()
    test_backend_config()

    # Summary
    passed = sum(1 for s, _, _ in results if s == PASS)
    failed = sum(1 for s, _, _ in results if s == FAIL)
    warned = sum(1 for s, _, _ in results if s == WARN)

    print("\n" + "=" * 60)
    print(f"  SUMMARY:  {passed} passed  |  {warned} warnings  |  {failed} failed")
    print("=" * 60)

    if failed:
        print("\nFailed checks:")
        for s, t, d in results:
            if s == FAIL:
                print(f"  - {t}: {d}")

    if failed == 0:
        print("\nCore upload -> embed -> store -> retrieve pipeline is WORKING.")
    else:
        print("\nFix the FAILED items above before starting the server.")

    return failed


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(0 if exit_code == 0 else 1)
