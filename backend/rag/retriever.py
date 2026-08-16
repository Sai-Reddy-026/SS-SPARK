"""
rag/retriever.py
Hybrid Retriever combining Vector Search with BM25 Keyword Search for SS SPARK.
"""

from __future__ import annotations

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


async def retrieve(
    query: str,
    top_k: int = 5,
    n_results: Optional[int] = None,
    user_id: Optional[str] = None,
) -> RetrievalResult:
    """
    Retrieve the most relevant context chunks for a query using embedding similarity.
    Supports both top_k and n_results arguments.
    """
    limit = n_results if n_results is not None else top_k
    if not query.strip():
        return RetrievalResult([])

    try:
        embedder = get_embedder()
        vs = get_vector_store()

        query_vectors = embedder.embed([query])
        if not query_vectors:
            return RetrievalResult([])

        hits = vs.search(query_vectors[0], n_results=limit, user_id=user_id)
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
        return RetrievalResult(chunks)
    except Exception as exc:
        logger.warning("Retrieval encountered an error: %s", exc)
        return RetrievalResult([])


# Alias for backwards compatibility
qdrant_retrieve = retrieve

