"""
rag/retriever.py
Hybrid Retriever combining Vector Search with BM25 Keyword Search for SS SPARK.
"""

from __future__ import annotations

import asyncio
import logging
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
    """Combine dense vector similarity with lexical term overlap for high-precision citation ranking."""
    import re
    q_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) >= 3 and w not in _RETRIEVAL_STOPWORDS]
    if not q_tokens or not chunks:
        return chunks

    scored = []
    for c in chunks:
        c_text = f"{c.text} {c.source}".lower()
        matches = sum(1 for t in q_tokens if t in c_text or (len(t) >= 4 and t[:4] in c_text))
        lex_score = matches / len(q_tokens)
        combined_score = 0.60 * c.relevance + 0.40 * lex_score
        c.relevance = round(combined_score, 4)
        scored.append((combined_score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored]


async def retrieve(
    query: str,
    top_k: int = 5,
    n_results: Optional[int] = None,
    user_id: Optional[str] = None,
) -> RetrievalResult:
    """
    Retrieve the most relevant context chunks for a query using hybrid embedding similarity & lexical matching.
    Non-blocking offload to worker threads prevents freezing the asyncio event loop.
    """
    limit = n_results if n_results is not None else top_k
    if not query.strip():
        return RetrievalResult([])

    try:
        embedder = get_embedder()
        vs = get_vector_store()

        query_vectors = await asyncio.to_thread(embedder.embed, [query])
        if not query_vectors:
            return RetrievalResult([])

        fetch_limit = max(limit * 2, 6)
        hits = await asyncio.to_thread(vs.search, query_vectors[0], n_results=fetch_limit, user_id=user_id)
        chunks = [
            RetrievedChunk(
                id=h.get("id", ""),
                doc_id=h.get("doc_id", ""),
                source=h.get("source", "document"),
                page=h.get("page", 1),
                text=h.get("text", ""),
                relevance=float(h.get("relevance", 0.0)),
            )
            for h in hits
        ]
        reranked = _hybrid_rerank(query, chunks)
        return RetrievalResult(reranked[:limit])
    except Exception as exc:
        logger.warning("Retrieval encountered an error: %s", exc)
        return RetrievalResult([])


# Alias for backwards compatibility
qdrant_retrieve = retrieve


