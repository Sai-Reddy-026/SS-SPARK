"""
rag/vector_store.py
Unified Vector Store Adapter for SS SPARK.

Supports:
- Qdrant (high-performance vector database with multi-tenancy & payload filtering)
- ChromaDB (secondary embedded fallback)
- In-memory fallback if neither database engine is reachable
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ss_spark.vector_store")

_vector_store_instance: Optional[VectorStore] = None


class VectorStore:
    """Unified interface for vector storage and similarity search."""

    def __init__(
        self,
        persist_directory: str = "chroma_db",
        collection_name: str = "ss_spark_chunks",
        use_qdrant: bool = True,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        qdrant_api_key: str = "",
    ):
        self.persist_dir = persist_directory
        self.collection_name = collection_name
        self.use_qdrant = use_qdrant
        self.qdrant_client = None
        self.chroma_collection = None
        self._mem_chunks: List[Dict[str, Any]] = []

        # 1. Initialize Qdrant if enabled
        if self.use_qdrant:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import Distance, VectorParams

                if qdrant_api_key:
                    self.qdrant_client = QdrantClient(url=f"https://{qdrant_host}:{qdrant_port}", api_key=qdrant_api_key)
                else:
                    self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port, timeout=2.0)

                # Ensure collection exists
                collections = [c.name for c in self.qdrant_client.get_collections().collections]
                if self.collection_name not in collections:
                    self.qdrant_client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                    )
                logger.info("Connected to Qdrant collection '%s'", self.collection_name)
            except Exception as exc:
                logger.info("Qdrant connection not available (%s) — falling back to ChromaDB.", exc)
                self.qdrant_client = None

        # 2. Fall back to ChromaDB if Qdrant is not active
        if self.qdrant_client is None:
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
                client = chromadb.PersistentClient(
                    path=self.persist_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self.chroma_collection = client.get_or_create_collection(name=self.collection_name)
                logger.info("Connected to ChromaDB collection '%s'", self.collection_name)
            except Exception as exc:
                logger.warning("ChromaDB initialization failed (%s) — falling back to in-memory vector store.", exc)
                self.chroma_collection = None

    def add_chunks(
        self,
        doc_id: str,
        source_name: str,
        chunks: List[str],
        embeddings: List[List[float]],
        pages: List[int],
        user_id: Optional[str] = None,
    ) -> List[str]:
        """Store chunk vectors along with metadata."""
        if not chunks:
            return []

        ids = [f"{doc_id}_{i}_{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]

        # 1. Qdrant
        if self.qdrant_client is not None:
            try:
                from qdrant_client.models import PointStruct
                points = [
                    PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, cid)),
                        vector=emb,
                        payload={
                            "chunk_id": cid,
                            "doc_id": doc_id,
                            "source_name": source_name,
                            "page": page,
                            "text": text,
                            "user_id": user_id or "",
                        },
                    )
                    for cid, text, emb, page in zip(ids, chunks, embeddings, pages)
                ]
                self.qdrant_client.upsert(collection_name=self.collection_name, points=points)
                return ids
            except Exception as exc:
                logger.warning("Qdrant upsert failed (%s), writing to fallback.", exc)

        # 2. ChromaDB
        if self.chroma_collection is not None:
            try:
                metadatas = [
                    {
                        "doc_id": doc_id,
                        "source": source_name,
                        "page": page,
                        "user_id": user_id or "",
                    }
                    for page in pages
                ]
                self.chroma_collection.add(
                    ids=ids,
                    documents=chunks,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
                return ids
            except Exception as exc:
                logger.warning("ChromaDB upsert failed (%s), writing to memory.", exc)

        # 3. In-memory
        for cid, text, emb, page in zip(ids, chunks, embeddings, pages):
            self._mem_chunks.append({
                "id": cid,
                "doc_id": doc_id,
                "source": source_name,
                "text": text,
                "embedding": emb,
                "page": page,
                "user_id": user_id,
            })
        return ids

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search vector store for most similar text chunks."""
        results: List[Dict[str, Any]] = []

        # 1. Qdrant Search
        if self.qdrant_client is not None:
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                query_filter = None
                if user_id:
                    query_filter = Filter(
                        must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                    )
                hits = self.qdrant_client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    limit=n_results,
                    query_filter=query_filter,
                )
                for h in hits:
                    payload = h.payload or {}
                    results.append({
                        "id": payload.get("chunk_id", str(h.id)),
                        "doc_id": payload.get("doc_id", ""),
                        "source": payload.get("source_name", "document"),
                        "page": payload.get("page", 1),
                        "text": payload.get("text", ""),
                        "relevance": round(float(h.score), 3),
                    })
                return results
            except Exception as exc:
                logger.warning("Qdrant search failed (%s), checking ChromaDB fallback.", exc)

        # 2. ChromaDB Search
        if self.chroma_collection is not None:
            try:
                where_clause = {"user_id": user_id} if user_id else None
                chroma_res = self.chroma_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where_clause,
                )
                if chroma_res and chroma_res["documents"] and chroma_res["documents"][0]:
                    docs = chroma_res["documents"][0]
                    metas = chroma_res["metadatas"][0] if chroma_res["metadatas"] else [{}] * len(docs)
                    ids = chroma_res["ids"][0] if chroma_res["ids"] else [""] * len(docs)
                    distances = chroma_res["distances"][0] if chroma_res.get("distances") else [0.0] * len(docs)
                    for cid, text, meta, dist in zip(ids, docs, metas, distances):
                        relevance = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
                        results.append({
                            "id": cid,
                            "doc_id": meta.get("doc_id", ""),
                            "source": meta.get("source", "document"),
                            "page": meta.get("page", 1),
                            "text": text,
                            "relevance": round(float(relevance), 3),
                        })
                return results
            except Exception as exc:
                logger.warning("ChromaDB search failed (%s), checking memory fallback.", exc)

        # 3. In-memory Cosine Similarity
        def cosine_sim(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(y * y for y in b) ** 0.5
            return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

        candidates = [
            c for c in self._mem_chunks
            if user_id is None or c.get("user_id") == user_id or c.get("user_id") is None
        ]
        scored = [
            (cosine_sim(query_embedding, c["embedding"]), c)
            for c in candidates
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        for score, c in scored[:n_results]:
            results.append({
                "id": c["id"],
                "doc_id": c["doc_id"],
                "source": c["source"],
                "page": c["page"],
                "text": c["text"],
                "relevance": round(float(score), 3),
            })
        return results

    def delete_by_doc_id(self, doc_id: str) -> None:
        """Remove all chunks associated with a document ID."""
        if self.qdrant_client is not None:
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                self.qdrant_client.delete(
                    collection_name=self.collection_name,
                    points_selector=Filter(
                        must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                    ),
                )
            except Exception as exc:
                logger.warning("Qdrant delete failed: %s", exc)

        if self.chroma_collection is not None:
            try:
                self.chroma_collection.delete(where={"doc_id": doc_id})
            except Exception as exc:
                logger.warning("ChromaDB delete failed: %s", exc)

        self._mem_chunks = [c for c in self._mem_chunks if c.get("doc_id") != doc_id]

    def count(self) -> int:
        """Return total vector count."""
        if self.qdrant_client is not None:
            try:
                info = self.qdrant_client.get_collection(self.collection_name)
                return info.points_count or 0
            except Exception:
                pass
        if self.chroma_collection is not None:
            try:
                return self.chroma_collection.count()
            except Exception:
                pass
        return len(self._mem_chunks)


def get_vector_store(
    persist_directory: str = "chroma_db",
    collection_name: str = "ss_spark_chunks",
) -> VectorStore:
    """Return singleton vector store instance."""
    global _vector_store_instance
    if _vector_store_instance is None:
        from core.config import get_settings
        cfg = get_settings()
        _vector_store_instance = VectorStore(
            persist_directory=str(cfg.CHROMA_DIR),
            collection_name=cfg.QDRANT_COLLECTION if cfg.USE_QDRANT else cfg.CHROMA_COLLECTION,
            use_qdrant=cfg.USE_QDRANT,
            qdrant_host=cfg.QDRANT_HOST,
            qdrant_port=cfg.QDRANT_PORT,
            qdrant_api_key=cfg.QDRANT_API_KEY,
        )
    return _vector_store_instance
