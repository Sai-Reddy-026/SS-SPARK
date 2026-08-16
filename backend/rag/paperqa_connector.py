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
# Global Docs instance
# --------------------------------------------------------------------------- #

_docs: Any = None          # paperqa.Docs
_indexed_paths: set[str] = set()


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
            "PaperQA is not installed. Run: pip install -e "
            "\"c:/Users/saidu/OneDrive/Desktop/ai_project/paper-qa\""
        ) from exc

    openai_key = os.getenv("OPENAI_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    # Pick the best available LLM
    if openai_key:
        llm_name = "gpt-4o-mini"
        embed_name = "text-embedding-3-small"
        logger.info("PaperQA connector: using OpenAI (model=%s)", llm_name)
    elif gemini_key:
        llm_name = "gemini/gemini-flash-latest"
        embed_name = "gemini/gemini-embedding-001"
        os.environ["GEMINI_API_KEY"] = gemini_key
        os.environ["GOOGLE_API_KEY"] = gemini_key  # litellm also reads GOOGLE_API_KEY
        logger.info("PaperQA connector: using Gemini (model=%s)", llm_name)
    elif anthropic_key:
        llm_name = "claude-3-5-haiku-20241022"
        embed_name = "text-embedding-3-small"  # Anthropic has no embedding API; fallback
        logger.info("PaperQA connector: using Anthropic (model=%s)", llm_name)
    else:
        raise RuntimeError(
            "No LLM API key found. Set OPENAI_API_KEY, GEMINI_API_KEY, "
            "or ANTHROPIC_API_KEY in your .env file."
        )

    return Settings(
        llm=llm_name,
        summary_llm=llm_name,
        embedding=embed_name,
    )


def _get_or_create_docs() -> Any:
    """Return (and lazily create) the global PaperQA Docs instance."""
    global _docs
    if _docs is None:
        from paperqa import Docs
        _docs = Docs()
        logger.info("Created new PaperQA Docs instance.")
    return _docs


def reset_docs() -> None:
    """Destroy the global Docs cache (called after document deletion)."""
    global _docs, _indexed_paths
    _docs = None
    _indexed_paths = set()
    logger.info("PaperQA Docs cache cleared.")


# --------------------------------------------------------------------------- #
# Document ingestion
# --------------------------------------------------------------------------- #

async def add_document(file_path: str) -> bool:
    """
    Index a document into the PaperQA Docs collection.

    Uses `Docs.aadd()` — PaperQA's native async add which:
      1. Reads and parses the PDF/text
      2. Generates an LLM-based citation if none is provided
      3. Embeds text chunks into its NumpyVectorStore
      4. Stores Doc + Text objects in memory

    Args:
        file_path: Absolute path to the document file.

    Returns:
        True on success, False if document was already indexed or failed.
    """
    global _indexed_paths

    if file_path in _indexed_paths:
        logger.debug("Already indexed: %s", file_path)
        return True

    if not Path(file_path).exists():
        logger.warning("File does not exist: %s", file_path)
        return False

    docs = _get_or_create_docs()
    settings = _build_settings()

    try:
        docname = await docs.aadd(
            path=file_path,
            settings=settings,
            citation=None,   # let PaperQA auto-generate citation via LLM
        )
        if docname:
            _indexed_paths.add(file_path)
            logger.info("PaperQA indexed '%s' as '%s'", Path(file_path).name, docname)
            return True
        else:
            logger.warning("PaperQA skipped '%s' (already exists or empty)", file_path)
            _indexed_paths.add(file_path)  # mark as processed to avoid retries
            return False
    except Exception as exc:
        logger.error("PaperQA failed to index '%s': %s", file_path, exc)
        return False


async def add_text_content(text: str, source_name: str) -> bool:
    """
    Index raw text (e.g. OCR output) into the PaperQA Docs collection
    by writing it to a temporary .txt file and calling aadd().

    Args:
        text:        The extracted text content.
        source_name: A label used as the document name.

    Returns:
        True on success.
    """
    import tempfile

    # Write to a temp file with the source name embedded
    tmp_dir = Path(tempfile.gettempdir()) / "papergenius_ocr"
    tmp_dir.mkdir(exist_ok=True)
    safe_stem = "".join(c if c.isalnum() or c in "._-" else "_" for c in source_name)
    tmp_file = tmp_dir / f"{safe_stem}.txt"
    tmp_file.write_text(text, encoding="utf-8")

    return await add_document(str(tmp_file))


async def reindex_all(file_paths: list[str]) -> None:
    """
    Reset the Docs cache and re-index all given file paths.
    Called on startup and after document deletion.
    """
    reset_docs()
    for path in file_paths:
        await add_document(path)
    logger.info(
        "Re-indexing complete. %d/%d documents indexed.",
        len(_indexed_paths), len(file_paths)
    )


# --------------------------------------------------------------------------- #
# Question answering
# --------------------------------------------------------------------------- #

async def query(question: str) -> dict[str, Any]:
    """
    Send a question to PaperQA's agentic RAG pipeline.

    IMPORTANT: Callers must ensure get_indexed_count() > 0 before calling this.
    The no-docs routing is handled upstream in chat_service.py.

    Flow:
        question → agent_query() → SearchIndex → GatherEvidence tool
                 → GenerateAnswer tool → AnswerResponse

    The AnswerResponse.session (a PQASession) contains:
        - session.answer          : final answer string
        - session.contexts        : list[Context] with source citations
        - session.references      : formatted bibliography string
        - session.formatted_answer: answer + citations combined

    Returns:
        {
            "answer": str,
            "sources": [{"source": str, "page": int, "snippet": str, "relevance": float}],
            "confidence": float,
            "references": str,
            "cost": float,
            "status": str,
        }
    """
    from paperqa.agents import agent_query
    from paperqa.agents.models import AgentStatus

    docs = _get_or_create_docs()
    settings = _build_settings()

    try:
        response = await agent_query(
            query=question,
            settings=settings,
            docs=docs,
        )
    except Exception as exc:
        logger.error("PaperQA agent_query failed: %s", exc)
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

def get_indexed_count() -> int:
    return len(_indexed_paths)


def get_indexed_paths() -> list[str]:
    return list(_indexed_paths)


def is_document_indexed(file_path: str) -> bool:
    return file_path in _indexed_paths
