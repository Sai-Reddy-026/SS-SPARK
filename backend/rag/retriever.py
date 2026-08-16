"""
rag/retriever.py
Hybrid Retriever combining Vector Search with BM25 Keyword Search for SS SPARK.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from rag.embeddings import get_embedder
from rag.vector_store import get_vector_store

logger = logging.getLogger("ss_spark.retriever")


async def retrieve(
    query: str,
    top_k: int = 5,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve the most relevant context chunks for a query using embedding similarity.
    """
    if not query.strip():
        return []

    try:
        embedder = get_embedder()
        vs = get_vector_store()

        query_vectors = embedder.embed([query])
        if not query_vectors:
            return []

        hits = vs.search(query_vectors[0], n_results=top_k, user_id=user_id)
        return hits
    except Exception as exc:
        logger.warning("Retrieval encountered an error: %s", exc)
        return []
