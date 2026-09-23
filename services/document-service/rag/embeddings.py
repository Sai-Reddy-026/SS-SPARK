"""
rag/embeddings.py
Unified Embedding provider for SS SPARK.

Supports:
- Local SentenceTransformers (all-MiniLM-L6-v2) — offline, fast, 384 dimensions
- OpenAI text-embedding-3-small / text-embedding-ada-002
- Google Gemini text-embedding-004 / embedding-001
- Deterministic fallback embedder for zero-dependency test environments
"""

from __future__ import annotations

import logging
import math
import os
from typing import List, Optional

logger = logging.getLogger("ss_spark.embeddings")

_embedder_instance: Optional[BaseEmbedder] = None


class BaseEmbedder:
    """Base interface for all embedding providers."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class SentenceTransformerEmbedder(BaseEmbedder):
    """Local embedding using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        logger.info("Initializing SentenceTransformer: %s", model_name)
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.tolist()


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embeddings API."""

    def __init__(self, model: str = "text-embedding-3-small", api_key: Optional[str] = None):
        from openai import OpenAI
        self.model = model
        key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=key)

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in response.data]


class GeminiEmbedder(BaseEmbedder):
    """Google Gemini embeddings API with concurrent batching."""

    def __init__(self, model: str = "models/text-embedding-004", api_key: Optional[str] = None):
        import google.generativeai as genai
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=key)
        self.model = model

    def embed(self, texts: List[str]) -> List[List[float]]:
        import google.generativeai as genai
        from concurrent.futures import ThreadPoolExecutor

        if not texts:
            return []

        # Single item fast-path
        if len(texts) == 1:
            try:
                res = genai.embed_content(model=self.model, content=texts[0])
                return [res["embedding"]]
            except Exception as exc:
                logger.warning("Gemini single embed failed: %s", exc)
                return [[0.0] * 384]

        # 1. Try native batch request (1 single HTTP roundtrip per 100 chunks)
        try:
            batch_size = 100
            all_embeddings: List[List[float]] = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                res = genai.embed_content(model=self.model, content=batch)
                emb = res.get("embedding", [])
                if emb and isinstance(emb[0], float):
                    all_embeddings.append(emb)
                else:
                    all_embeddings.extend(emb)
            if len(all_embeddings) == len(texts):
                return all_embeddings
        except Exception as exc:
            logger.debug("Gemini native batch embed fallback: %s", exc)

        # 2. Fallback to bounded concurrent worker pool
        def _embed_single(text: str) -> List[float]:
            try:
                res = genai.embed_content(model=self.model, content=text)
                return res["embedding"]
            except Exception as exc:
                logger.warning("Gemini embed chunk failed: %s", exc)
                return [0.0] * 384

        max_workers = min(len(texts), 16)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_embed_single, texts))

        return results


class FallbackEmbedder(BaseEmbedder):
    """Lightweight deterministic pseudo-embedder used if no models can be loaded."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        results = []
        for text in texts:
            vec = [0.0] * self.dim
            for i, char in enumerate(text[: self.dim]):
                vec[i % self.dim] += (ord(char) % 100) / 100.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            results.append([x / norm for x in vec])
        return results


def get_embedder() -> BaseEmbedder:
    """Return singleton embedder instance based on active configuration."""
    global _embedder_instance
    if _embedder_instance is not None:
        return _embedder_instance

    # 1. Try local SentenceTransformers (most reliable and zero API cost)
    try:
        _embedder_instance = SentenceTransformerEmbedder()
        return _embedder_instance
    except Exception as exc:
        logger.info("Local sentence-transformers not available (%s), trying OpenAI...", exc)

    # 2. Try OpenAI
    if os.getenv("OPENAI_API_KEY"):
        try:
            _embedder_instance = OpenAIEmbedder()
            return _embedder_instance
        except Exception as exc:
            logger.info("OpenAI embedder failed: %s", exc)

    # 3. Try Gemini
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        try:
            _embedder_instance = GeminiEmbedder()
            return _embedder_instance
        except Exception as exc:
            logger.info("Gemini embedder failed: %s", exc)

    # 4. Fallback
    logger.warning("Using fallback lightweight embedder.")
    _embedder_instance = FallbackEmbedder()
    return _embedder_instance
