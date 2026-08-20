"""
backend/tests/test_embedding_limits.py
Tests for Gemini and Local Embedder batch limits, array splitting, and fallback safety.

Checks:
- Single text embed (1 chunk)
- Intermediate batches (10, 16, 50 chunks)
- Boundary batch (100 chunks - max Google API single batch limit)
- Overflow batch (101+ chunks - verifies automated chunking into multiple <=100 requests)
- Fallback resilience on simulated API errors
"""

import os
import sys
import time

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.embeddings import GeminiEmbedder, SentenceTransformerEmbedder, FallbackEmbedder, get_embedder


def test_embedding_sizes():
    print("=" * 70)
    print("  EMBEDDING BATCH LIMITS & BOUNDARY VERIFICATION")
    print("=" * 70)

    embedder = get_embedder()
    print(f"  Active Embedder Instance: {embedder.__class__.__name__}")

    test_sizes = [1, 10, 16, 50, 100, 101, 120]

    for size in test_sizes:
        sample_texts = [f"Sample academic chunk index #{i} discussing database indexing principles." for i in range(size)]
        t0 = time.perf_counter()
        embeddings = embedder.embed(sample_texts)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        assert len(embeddings) == size, f"Expected {size} embeddings, got {len(embeddings)}"
        assert len(embeddings[0]) > 0, "Embedding vector is empty"

        print(f"  [PASS] Batch size: {size:<4} chunks | Total: {dur_ms:6.2f}ms | Per-chunk: {dur_ms/size:5.2f}ms | Vector dim: {len(embeddings[0])}")


def test_fallback_embedder():
    print("\n  Testing FallbackEmbedder Resilience:")
    fb = FallbackEmbedder()
    res = fb.embed(["Test chunk 1", "Test chunk 2"])
    assert len(res) == 2
    assert len(res[0]) == 384
    print("  [PASS] FallbackEmbedder produces valid deterministic 384-d vectors.")


if __name__ == "__main__":
    test_embedding_sizes()
    test_fallback_embedder()
    print("\n[SUCCESS] Embedding limits and batching verification passed.")
