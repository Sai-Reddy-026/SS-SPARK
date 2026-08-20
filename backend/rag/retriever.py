"""
rag/retriever.py
Hybrid Retriever combining Dense Vector Search with Exam/Question Paper Lexical Reranking for SS SPARK.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from rag.embeddings import get_embedder
from rag.vector_store import get_vector_store

logger = logging.getLogger("ss_spark.retriever")


class RetrievedChunk(BaseModel):
    id: str = ""
    doc_id: str = ""
    source: str = "document"
    page: int = 1
    text: str = ""
    relevance: float = 0.0
    is_ocr: bool = False

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class RetrievalResult:
    """Container for retrieval results supporting list iteration and .chunks access."""

    def __init__(self, chunks: List[RetrievedChunk]):
        self.chunks = chunks

    def __iter__(self):
        return iter(self.chunks)

    def __len__(self):
        return len(self.chunks)

    def __getitem__(self, index):
        return self.chunks[index]

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [c.model_dump() for c in self.chunks]


_RETRIEVAL_STOPWORDS = {
    "what", "when", "where", "which", "while", "whose", "why", "how", "does", "explain",
    "the", "and", "for", "are", "is", "in", "of", "to", "a", "an", "with", "between",
    "from", "that", "this", "these", "those", "their", "relates", "summarize", "about",
}


def _hybrid_rerank(query: str, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    """
    Combine dense vector similarity with lexical term overlap and question paper structure matching:
      - Boosts exact question numbers (e.g. 'Question 5', 'Q5', '5.', 'Part A', 'Section B')
      - Rewards table and diagram keyword overlap
      - Calibrates OCR-derived chunk relevance
    """
    q_lower = query.lower()
    q_tokens = [w for w in re.findall(r"\w+", q_lower) if len(w) >= 3 and w not in _RETRIEVAL_STOPWORDS]
    if not chunks:
        return chunks

    # Detect question number targets in query (e.g. "question 5", "q5", "5th question")
    q_num_matches = re.findall(r"(?:question\s*|q\s*|#\s*)(\d+)", q_lower)
    target_q_nums = set(q_num_matches)

    # Detect section/part targets (e.g. "part a", "section b")
    sec_matches = re.findall(r"(?:part|section)\s*[-:]?\s*([a-d])", q_lower)
    target_secs = set(sec_matches)

    scored = []
    for c in chunks:
        c_text = f"{c.text} {c.source}".lower()

        # 1. Lexical term match ratio
        if q_tokens:
            matches = sum(1 for t in q_tokens if t in c_text or (len(t) >= 4 and t[:4] in c_text))
            lex_score = matches / len(q_tokens)
        else:
            lex_score = 0.5

        # 2. Question number structural boost (+0.25 if exact question item matches)
        q_boost = 0.0
        if target_q_nums:
            for qn in target_q_nums:
                # Check for patterns like "5.", "Q5.", "Question 5", "5 )"
                if re.search(rf"(?:q\s*{qn}\b|question\s*{qn}\b|\b{qn}\s*[\.\)])", c_text):
                    q_boost = 0.25
                    break

        # 3. Section/Part boost (+0.15)
        sec_boost = 0.0
        if target_secs:
            for s in target_secs:
                if re.search(rf"(?:part|section)\s*[-:]?\s*{s}\b", c_text):
                    sec_boost = 0.15
                    break

        # Combined hybrid score (clamped between 0.0 and 1.0)
        raw_combined = (0.50 * c.relevance) + (0.35 * lex_score) + q_boost + sec_boost
        combined_score = min(1.0, max(0.0, raw_combined))
        c.relevance = round(combined_score, 4)
        scored.append((combined_score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored]


async def retrieve(
    query: str,
    top_k: int = 5,
    n_results: Optional[int] = None,
    user_id: Optional[str] = None,
    req_id: str = "",
) -> RetrievalResult:
    """
    Retrieve the most relevant context chunks for a query using hybrid embedding similarity & lexical matching.
    Non-blocking offload to worker threads prevents freezing the asyncio event loop.
    """
    limit = n_results if n_results is not None else top_k
    tag = f"[{req_id}] " if req_id else ""
    if not query.strip():
        return RetrievalResult([])

    try:
        embedder = get_embedder()
        vs = get_vector_store()

        logger.info("%sembedding_start", tag)
        t_emb = time.perf_counter()
        query_vectors = await asyncio.to_thread(embedder.embed, [query])
        emb_ms = round((time.perf_counter() - t_emb) * 1000, 2)
        logger.info("%sembedding_complete in %.2fms", tag, emb_ms)

        if not query_vectors:
            return RetrievalResult([])

        fetch_limit = max(limit * 2, 6)
        logger.info("%svector_search_start", tag)
        t_vs = time.perf_counter()
        hits = await asyncio.to_thread(vs.search, query_vectors[0], n_results=fetch_limit, user_id=user_id)
        vs_ms = round((time.perf_counter() - t_vs) * 1000, 2)
        logger.info("%svector_search_complete in %.2fms | found %d raw chunks", tag, vs_ms, len(hits))

        chunks = [
            RetrievedChunk(
                id=h.get("id", ""),
                doc_id=h.get("doc_id", ""),
                source=h.get("source", "document"),
                page=h.get("page", 1),
                text=h.get("text", ""),
                relevance=float(h.get("relevance", 0.0)),
                is_ocr=bool(h.get("is_ocr", False)),
            )
            for h in hits
        ]
        reranked = _hybrid_rerank(query, chunks)
        return RetrievalResult(reranked[:limit])
    except Exception as exc:
        logger.warning("%sretrieval error: %s", tag, exc)
        return RetrievalResult([])


# Alias for backwards compatibility
qdrant_retrieve = retrieve
