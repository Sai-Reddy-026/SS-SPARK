"""
rag/paperqa_connector.py

Integration layer between the FastAPI backend and the EXISTING PaperQA project.

Architecture:
    FastAPI → paperqa_connector → paperqa.Docs / paperqa.agents.ask
                                → paperqa.Settings (LiteLLM-based LLMs)
                                → NumpyVectorStore (PaperQA's built-in vector store)

This module does NOT rewrite PaperQA.  It imports and uses PaperQA's
public API as-is from the installed package:
    - Docs.aadd()          — async document indexing
    - agent_query()        — agentic RAG answer generation
    - Settings             — unified LLM + embedding config

Key design decisions:
    - A single global `Docs` instance is maintained per backend process.
    - All PaperQA calls are already async (using asyncio / anyio) so
      no thread-pool workaround is needed here.
    - The local PaperQA project at ai_project/paper-qa is installed in
      editable mode (`pip install -e`), so `import paperqa` resolves to
      that exact codebase.
    - LLMs are configured through PaperQA's `Settings` class via LiteLLM,
      which supports OpenAI, Gemini (gemini/*), and Anthropic out of the box.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# User-scoped Docs instances (Per-user isolation)
# --------------------------------------------------------------------------- #

_user_docs: dict[str, Any] = {}
_user_indexed_paths: dict[str, set[str]] = {}


def _normalize_uid(user_id: Optional[str]) -> str:
    return user_id.strip() if (user_id and user_id.strip()) else "global"


def _build_settings():
    """
    Build a PaperQA Settings object using available API keys.

    LiteLLM model name conventions:
        OpenAI:    "gpt-4o", "gpt-4o-mini"
        Gemini:    "gemini/gemini-2.0-flash", "gemini/gemini-1.5-pro"
        Anthropic: "claude-3-5-sonnet-20241022"
    """
    try:
        from paperqa import Settings
    except ImportError as exc:
        raise RuntimeError(
            "PaperQA is not installed or importable. Ensure packages/paperqa is installed via pip."
        ) from exc

    from core.config import get_settings
    cfg = get_settings()

    openai_key = cfg.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
    gemini_key = cfg.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    anthropic_key = cfg.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY", "")
    nvidia_key = cfg.NVIDIA_API_KEY or os.getenv("NVIDIA_API_KEY", "") or os.getenv("NVIDIA_NIM_API_KEY", "")

    from paperqa.settings import ParsingSettings

    # Pick embedding model based on available keys
    if openai_key:
        embed_name = "text-embedding-3-small"
    else:
        embed_name = "st-all-MiniLM-L6-v2"

    # Pick the best available LLM
    if openai_key:
        llm_name = "gpt-4o-mini"
        logger.info("PaperQA connector: using OpenAI (model=%s)", llm_name)
    elif nvidia_key:
        llm_name = "nvidia_nim/meta/llama-3.1-8b-instruct"
        os.environ["NVIDIA_API_KEY"] = nvidia_key
        os.environ["NVIDIA_NIM_API_KEY"] = nvidia_key
        logger.info("PaperQA connector: using NVIDIA NIM (model=%s)", llm_name)
    elif gemini_key:
        llm_name = "gemini/gemini-3.5-flash"
        os.environ["GEMINI_API_KEY"] = gemini_key
        os.environ["GOOGLE_API_KEY"] = gemini_key  # litellm also reads GOOGLE_API_KEY
        logger.info("PaperQA connector: using Gemini (model=%s)", llm_name)
    elif anthropic_key:
        llm_name = "claude-3-5-haiku-20241022"
        logger.info("PaperQA connector: using Anthropic (model=%s)", llm_name)
    else:
        raise RuntimeError(
            "No LLM API key found. Set OPENAI_API_KEY, GEMINI_API_KEY, NVIDIA_API_KEY, "
            "or ANTHROPIC_API_KEY in your .env file."
        )

    # Disable online journal queries (Crossref/Semantic Scholar) for fast local doc indexing
    parsing_cfg = ParsingSettings(
        use_doc_details=False,
    )

    return Settings(
        llm=llm_name,
        summary_llm=llm_name,
        embedding=embed_name,
        parsing=parsing_cfg,
    )


def _get_or_create_user_docs(user_id: Optional[str] = None) -> Any:
    """Return (and lazily create) the user-scoped PaperQA Docs instance."""
    from paperqa import Docs
    uid = _normalize_uid(user_id)
    if uid not in _user_docs:
        _user_docs[uid] = Docs()
        logger.info("Created new PaperQA Docs instance for user: %s", uid)
    return _user_docs[uid]


def _get_or_create_docs(user_id: Optional[str] = None) -> Any:
    """Compatibility alias for user-scoped Docs getter."""
    return _get_or_create_user_docs(user_id)


def reset_docs(user_id: Optional[str] = None) -> None:
    """Destroy the Docs cache for a specific user, or all users if user_id is None."""
    global _user_docs, _user_indexed_paths
    if user_id is not None:
        uid = _normalize_uid(user_id)
        _user_docs.pop(uid, None)
        _user_indexed_paths.pop(uid, None)
        logger.info("PaperQA Docs cache cleared for user: %s", uid)
    else:
        _user_docs.clear()
        _user_indexed_paths.clear()
        logger.info("PaperQA all user Docs caches cleared.")


# --------------------------------------------------------------------------- #
# Document ingestion
# --------------------------------------------------------------------------- #

async def add_document(
    file_path: str,
    user_id: Optional[str] = None,
    citation: Optional[str] = None,
) -> bool:
    """
    Index a document into the user's PaperQA Docs collection.

    Uses `Docs.aadd()` — PaperQA's native async add which:
      1. Reads and parses the PDF/text
      2. Uses citation if provided, or generates an LLM-based citation
      3. Embeds text chunks into its NumpyVectorStore
      4. Stores Doc + Text objects in memory

    Args:
        file_path: Absolute path to the document file.
        user_id: Owner of the document for multi-tenant isolation.
        citation: Optional explicit citation string.

    Returns:
        True on success, False if document was already indexed or failed.
    """
    uid = _normalize_uid(user_id)
    if uid not in _user_indexed_paths:
        _user_indexed_paths[uid] = set()

    if file_path in _user_indexed_paths[uid]:
        logger.debug("Already indexed for user %s: %s", uid, file_path)
        return True

    if not Path(file_path).exists():
        logger.warning("File does not exist: %s", file_path)
        return False

    docs = _get_or_create_user_docs(uid)
    settings = _build_settings()

    try:
        doc_citation = citation or f"{Path(file_path).name}"
        docname = await docs.aadd(
            path=file_path,
            settings=settings,
            citation=doc_citation,
        )
        if docname:
            _user_indexed_paths[uid].add(file_path)
            logger.info("PaperQA indexed '%s' for user %s as '%s'", Path(file_path).name, uid, docname)
            return True
        else:
            logger.warning("PaperQA skipped '%s' for user %s (already exists or empty)", file_path, uid)
            _user_indexed_paths[uid].add(file_path)  # mark as processed to avoid retries
            return False
    except Exception as exc:
        logger.error("PaperQA failed to index '%s' for user %s: %s", file_path, uid, exc)
        return False


async def remove_document(file_path: str, user_id: Optional[str] = None) -> None:
    """Evict a document from PaperQA memory for the specified user."""
    uid = _normalize_uid(user_id)
    if uid in _user_indexed_paths and file_path in _user_indexed_paths[uid]:
        _user_indexed_paths[uid].discard(file_path)
        remaining = list(_user_indexed_paths[uid])
        # Re-initialize user docs from remaining active paths
        reset_docs(user_id=uid)
        for path in remaining:
            await add_document(path, user_id=uid)
        logger.info("Evicted '%s' from PaperQA for user %s (%d remaining)", Path(file_path).name, uid, len(remaining))


async def add_text_content(text: str, source_name: str, user_id: Optional[str] = None) -> bool:
    """
    Index raw text (e.g. OCR output) into the user's PaperQA Docs collection.
    """
    import tempfile

    tmp_dir = Path(tempfile.gettempdir()) / "ss_spark_ocr"
    tmp_dir.mkdir(exist_ok=True)
    safe_stem = "".join(c if c.isalnum() or c in "._-" else "_" for c in source_name)
    tmp_file = tmp_dir / f"{safe_stem}.txt"
    tmp_file.write_text(text, encoding="utf-8")

    return await add_document(str(tmp_file), user_id=user_id)


async def reindex_all(file_paths: list[str], user_id: Optional[str] = None) -> None:
    """
    Reset Docs and re-index all given file paths for the given user.
    """
    reset_docs(user_id=user_id)
    for path in file_paths:
        await add_document(path, user_id=user_id)
    uid = _normalize_uid(user_id)
    logger.info(
        "Re-indexing complete for user %s: %d/%d documents indexed.",
        uid, len(_user_indexed_paths.get(uid, set())), len(file_paths)
    )


# --------------------------------------------------------------------------- #
# Question answering
# --------------------------------------------------------------------------- #

async def query(question: str, user_id: Optional[str] = None) -> dict[str, Any]:
    """
    Send a question to the user-scoped PaperQA agentic RAG pipeline.

    Multi-user isolation:
        Only queries the Docs collection owned by `user_id`.
    """
    from paperqa.agents import agent_query

    uid = _normalize_uid(user_id)
    docs = _get_or_create_user_docs(uid)
    settings = _build_settings()

    try:
        response = await agent_query(
            query=question,
            settings=settings,
            docs=docs,
        )
    except Exception as exc:
        logger.error("PaperQA agent_query failed for user %s: %s", uid, exc)
        return {
            "answer": (
                f"I encountered an error while answering your question: {exc}\n\n"
                "Please verify your API key is valid and documents are properly uploaded."
            ),
            "sources": [],
            "confidence": 0.0,
            "references": "",
            "cost": 0.0,
            "status": "error",
        }

    session = response.session

    # ---- Extract sources from contexts ----
    sources = []
    for ctx in session.contexts:
        text_obj = ctx.text  # paperqa.types.Text
        source_name = getattr(text_obj, "name", "") or getattr(
            getattr(text_obj, "doc", None), "docname", "Unknown"
        )
        pages = getattr(text_obj, "pages", None)
        page = pages[0] if pages else 0
        snippet = getattr(text_obj, "text", "")[:400]
        score = getattr(ctx, "score", 0)

        sources.append(
            {
                "source": source_name,
                "page": page,
                "snippet": snippet,
                "relevance": round(float(score) / 10.0, 4) if score else 0.8,
            }
        )

    # Confidence = fraction of sources that scored above threshold
    confidence = (
        round(sum(s["relevance"] for s in sources) / len(sources), 4)
        if sources else 0.0
    )

    # Status mapping
    status_map = {
        "success": "success",
        "fail": "error",
        "truncated": "partial",
        "unsure": "unsure",
    }
    status = status_map.get(str(response.status), "unknown")

    return {
        "answer": session.answer or session.formatted_answer,
        "sources": sources,
        "confidence": confidence,
        "references": session.references,
        "cost": round(session.cost, 6),
        "status": status,
    }


# --------------------------------------------------------------------------- #
# Status helpers
# --------------------------------------------------------------------------- #

def get_indexed_count(user_id: Optional[str] = None) -> int:
    uid = _normalize_uid(user_id)
    return len(_user_indexed_paths.get(uid, set()))


def get_indexed_paths(user_id: Optional[str] = None) -> list[str]:
    uid = _normalize_uid(user_id)
    return list(_user_indexed_paths.get(uid, set()))


def is_document_indexed(file_path: str, user_id: Optional[str] = None) -> bool:
    uid = _normalize_uid(user_id)
    return file_path in _user_indexed_paths.get(uid, set())
