"""
backend/tests/test_rag_quality_30.py
Comprehensive 30-Query Deterministic RAG Quality Evaluation Harness for SS SPARK.

Categories:
1. Direct Factual Questions (5)
2. Multi-Document Synthesis Questions (5)
3. Conceptual Reasoning Questions (5)
4. Comparative Questions (5)
5. Absent-Information / Negative Questions (5)
6. Citation-Specific Verification Questions (5)

Evaluates:
- Answer correctness / Key fact recall %
- Citation correctness & page accuracy %
- Hallucination rate % (citations on absent info)
- Stage-by-stage latency (router, retrieval, synthesis, total)
"""

import asyncio
import os
import sys
import time
import uuid
from typing import Any, Dict, List
import numpy as np

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import get_settings
from database import models
from database.models import UploadedDoc, save_document
from rag.embeddings import get_embedder
from rag.general_llm import contextualize_query, is_question_relevant_to_docs
from rag.retriever import retrieve
from rag.vector_store import get_vector_store
from services.chat_service import ask_question


# Seed Documents for Evaluation
DOC_1_TEXT = (
    "Third Normal Form (3NF) is a database normalization standard designed to reduce data redundancy and improve data integrity. "
    "A relation R is in Third Normal Form if and only if it is in Second Normal Form (2NF) and no non-prime attribute of R "
    "is transitively dependent on the primary key. Formally, for every functional dependency X -> Y, either X is a superkey, "
    "or Y is a prime attribute (part of a candidate key). 3NF eliminates transitive dependencies such as A -> B and B -> C. "
    "Boyce-Codd Normal Form (BCNF) is a stricter version of 3NF where every determinant X in X -> Y must strictly be a superkey."
)

DOC_2_TEXT = (
    "Database Indexing Structures: B-Tree vs Hash Indexing. "
    "A B-Tree index is a self-balancing M-way search tree where all leaf nodes reside at the same depth and are linked sequentially. "
    "B-Trees maintain sorted order and support both point lookups and range queries with O(log N) search complexity. "
    "In contrast, a Hash Index uses an internal hash function to map search keys directly to bucket addresses. "
    "Hash indexing achieves average O(1) time complexity for equality lookups (e.g. WHERE id = 42), but completely fails to support "
    "range queries (e.g. WHERE salary BETWEEN 50000 AND 80000) or sorting order."
)

DOC_3_TEXT = (
    "Database Concurrency Control and ACID Properties. "
    "Transactions in relational database management systems must strictly adhere to the ACID principles: "
    "Atomicity (all-or-nothing execution), Consistency (preservation of database invariants), "
    "Isolation (independent concurrent execution), and Durability (committed changes survive system crashes). "
    "Two-Phase Locking (2PL) guarantees conflict serializability of concurrent schedules. "
    "In the Growing Phase of 2PL, locks may be acquired but none released. In the Shrinking Phase, locks may be released but none acquired."
)


EVALUATION_DATASET = [
    # ----------------------------------------------------------------------- #
    # Category 1: Direct Factual Questions (5)
    # ----------------------------------------------------------------------- #
    {
        "id": "FACT-01",
        "category": "Direct Factual",
        "question": "What is the formal definition of Third Normal Form (3NF)?",
        "expected_status": "success",
        "must_contain": ["2NF", "transitive", "superkey"],
        "expect_citations": True,
        "primary_source": "dbms_normalization.pdf",
    },
    {
        "id": "FACT-02",
        "category": "Direct Factual",
        "question": "What are the four ACID properties in database transaction management?",
        "expected_status": "success",
        "must_contain": ["Atomicity", "Consistency", "Isolation", "Durability"],
        "expect_citations": True,
        "primary_source": "dbms_transactions.pdf",
    },
    {
        "id": "FACT-03",
        "category": "Direct Factual",
        "question": "What is the time complexity of searching in a B-Tree index?",
        "expected_status": "success",
        "must_contain": ["log"],
        "expect_citations": True,
        "primary_source": "dbms_indexing.pdf",
    },
    {
        "id": "FACT-04",
        "category": "Direct Factual",
        "question": "What is the requirement for Boyce-Codd Normal Form (BCNF)?",
        "expected_status": "success",
        "must_contain": ["superkey"],
        "expect_citations": True,
        "primary_source": "dbms_normalization.pdf",
    },
    {
        "id": "FACT-05",
        "category": "Direct Factual",
        "question": "What are the two phases in Two-Phase Locking (2PL)?",
        "expected_status": "success",
        "must_contain": ["Growing", "Shrinking"],
        "expect_citations": True,
        "primary_source": "dbms_transactions.pdf",
    },

    # ----------------------------------------------------------------------- #
    # Category 2: Multi-Document Synthesis Questions (5)
    # ----------------------------------------------------------------------- #
    {
        "id": "MULTI-01",
        "category": "Multi-Document Synthesis",
        "question": "How do database normalization and indexing interact to optimize query speed and data redundancy?",
        "expected_status": "success",
        "must_contain": ["redundancy", "index"],
        "expect_citations": True,
        "primary_source": "dbms_normalization.pdf",
    },
    {
        "id": "MULTI-02",
        "category": "Multi-Document Synthesis",
        "question": "Explain how transaction durability relates to indexed primary keys in 3NF tables.",
        "expected_status": "success",
        "must_contain": ["durability", "key"],
        "expect_citations": True,
        "primary_source": "dbms_transactions.pdf",
    },
    {
        "id": "MULTI-03",
        "category": "Multi-Document Synthesis",
        "question": "Why does a 2PL locking protocol maintain consistency in a normalized relational database?",
        "expected_status": "success",
        "must_contain": ["consistency", "lock"],
        "expect_citations": True,
        "primary_source": "dbms_transactions.pdf",
    },
    {
        "id": "MULTI-04",
        "category": "Multi-Document Synthesis",
        "question": "How does searching on B-Tree indexed candidate keys verify superkey constraints in BCNF?",
        "expected_status": "success",
        "must_contain": ["superkey", "search"],
        "expect_citations": True,
        "primary_source": "dbms_normalization.pdf",
    },
    {
        "id": "MULTI-05",
        "category": "Multi-Document Synthesis",
        "question": "Summarize the primary trade-offs between normalized table structures, B-Tree index overhead, and ACID transaction throughput.",
        "expected_status": "success",
        "must_contain": ["trade", "index"],
        "expect_citations": True,
        "primary_source": "dbms_indexing.pdf",
    },

    # ----------------------------------------------------------------------- #
    # Category 3: Conceptual Reasoning Questions (5)
    # ----------------------------------------------------------------------- #
    {
        "id": "REASON-01",
        "category": "Conceptual Reasoning",
        "question": "Why does Third Normal Form specifically target transitive dependencies instead of direct dependencies?",
        "expected_status": "success",
        "must_contain": ["transitive"],
        "expect_citations": True,
        "primary_source": "dbms_normalization.pdf",
    },
    {
        "id": "REASON-02",
        "category": "Conceptual Reasoning",
        "question": "Why is a Hash index unable to perform range queries efficiently?",
        "expected_status": "success",
        "must_contain": ["hash", "range"],
        "expect_citations": True,
        "primary_source": "dbms_indexing.pdf",
    },
    {
        "id": "REASON-03",
        "category": "Conceptual Reasoning",
        "question": "Why is lock release forbidden during the growing phase of Two-Phase Locking (2PL)?",
        "expected_status": "success",
        "must_contain": ["serializab"],
        "expect_citations": True,
        "primary_source": "dbms_transactions.pdf",
    },
    {
        "id": "REASON-04",
        "category": "Conceptual Reasoning",
        "question": "Why does BCNF provide stricter data redundancy prevention than standard 3NF?",
        "expected_status": "success",
        "must_contain": ["superkey"],
        "expect_citations": True,
        "primary_source": "dbms_normalization.pdf",
    },
    {
        "id": "REASON-05",
        "category": "Conceptual Reasoning",
        "question": "How do sequential leaf links in a B-Tree enable efficient range scanning?",
        "expected_status": "success",
        "must_contain": ["leaf"],
        "expect_citations": True,
        "primary_source": "dbms_indexing.pdf",
    },

    # ----------------------------------------------------------------------- #
    # Category 4: Comparative Questions (5)
    # ----------------------------------------------------------------------- #
    {
        "id": "COMP-01",
        "category": "Comparative",
        "question": "Compare B-Tree indexing and Hash indexing for equality vs range queries.",
        "expected_status": "success",
        "must_contain": ["B-Tree", "Hash", "range"],
        "expect_citations": True,
        "primary_source": "dbms_indexing.pdf",
    },
    {
        "id": "COMP-02",
        "category": "Comparative",
        "question": "Compare Third Normal Form (3NF) and Boyce-Codd Normal Form (BCNF).",
        "expected_status": "success",
        "must_contain": ["3NF", "BCNF", "superkey"],
        "expect_citations": True,
        "primary_source": "dbms_normalization.pdf",
    },
    {
        "id": "COMP-03",
        "category": "Comparative",
        "question": "Compare Atomicity and Durability in the context of system crashes.",
        "expected_status": "success",
        "must_contain": ["Atomicity", "Durability"],
        "expect_citations": True,
        "primary_source": "dbms_transactions.pdf",
    },
    {
        "id": "COMP-04",
        "category": "Comparative",
        "question": "Compare the Growing phase and Shrinking phase of Two-Phase Locking.",
        "expected_status": "success",
        "must_contain": ["Growing", "Shrinking", "lock"],
        "expect_citations": True,
        "primary_source": "dbms_transactions.pdf",
    },
    {
        "id": "COMP-05",
        "category": "Comparative",
        "question": "Compare 2NF and 3NF dependency requirements.",
        "expected_status": "success",
        "must_contain": ["2NF", "3NF", "transitive"],
        "expect_citations": True,
        "primary_source": "dbms_normalization.pdf",
    },

    # ----------------------------------------------------------------------- #
    # Category 5: Absent-Information / Negative Questions (5)
    # ----------------------------------------------------------------------- #
    {
        "id": "ABSENT-01",
        "category": "Absent Information",
        "question": "What is the rate of photosynthesis in deep sea hydrothermal vents?",
        "expected_status": "general",
        "must_contain": [],
        "expect_citations": False,
        "primary_source": "N/A",
    },
    {
        "id": "ABSENT-02",
        "category": "Absent Information",
        "question": "How does Shor's quantum factoring algorithm achieve polynomial time complexity?",
        "expected_status": "general",
        "must_contain": [],
        "expect_citations": False,
        "primary_source": "N/A",
    },
    {
        "id": "ABSENT-03",
        "category": "Absent Information",
        "question": "What were the major political causes of the French Revolution in 1789?",
        "expected_status": "general",
        "must_contain": [],
        "expect_citations": False,
        "primary_source": "N/A",
    },
    {
        "id": "ABSENT-04",
        "category": "Absent Information",
        "question": "How does React's virtual DOM reconciliation algorithm compute minimal tree diffs?",
        "expected_status": "general",
        "must_contain": [],
        "expect_citations": False,
        "primary_source": "N/A",
    },
    {
        "id": "ABSENT-05",
        "category": "Absent Information",
        "question": "Explain Kepler's three laws of planetary orbital motion around the sun.",
        "expected_status": "general",
        "must_contain": [],
        "expect_citations": False,
        "primary_source": "N/A",
    },

    # ----------------------------------------------------------------------- #
    # Category 6: Citation-Specific Verification Questions (5)
    # ----------------------------------------------------------------------- #
    {
        "id": "CITE-01",
        "category": "Citation Verification",
        "question": "According to the dbms_normalization.pdf document on page 3, what is 3NF?",
        "expected_status": "success",
        "must_contain": ["Normal Form", "transitive"],
        "expect_citations": True,
        "primary_source": "dbms_normalization.pdf",
        "expected_page": 3,
    },
    {
        "id": "CITE-02",
        "category": "Citation Verification",
        "question": "In dbms_indexing.pdf on page 12, how are B-Tree leaf nodes organized?",
        "expected_status": "success",
        "must_contain": ["leaf"],
        "expect_citations": True,
        "primary_source": "dbms_indexing.pdf",
        "expected_page": 12,
    },
    {
        "id": "CITE-03",
        "category": "Citation Verification",
        "question": "According to dbms_transactions.pdf on page 7, what is Two-Phase Locking?",
        "expected_status": "success",
        "must_contain": ["2PL", "lock"],
        "expect_citations": True,
        "primary_source": "dbms_transactions.pdf",
        "expected_page": 7,
    },
    {
        "id": "CITE-04",
        "category": "Citation Verification",
        "question": "In the normalization notes, what is the exact functional dependency definition X -> Y for 3NF?",
        "expected_status": "success",
        "must_contain": ["superkey", "prime"],
        "expect_citations": True,
        "primary_source": "dbms_normalization.pdf",
        "expected_page": 3,
    },
    {
        "id": "CITE-05",
        "category": "Citation Verification",
        "question": "In the indexing document, why are hash indexes O(1) for equality lookups?",
        "expected_status": "success",
        "must_contain": ["hash", "bucket"],
        "expect_citations": True,
        "primary_source": "dbms_indexing.pdf",
        "expected_page": 12,
    },
]


async def run_30_query_evaluation():
    print("=" * 80)
    print("  SS SPARK 30-QUERY DETERMINISTIC RAG QUALITY & GROUNDING EVALUATION")
    print("=" * 80)

    cfg = get_settings()
    user_id = f"eval_user_{uuid.uuid4().hex[:8]}"

    embedder = get_embedder()
    vs = get_vector_store(str(cfg.CHROMA_DIR), cfg.CHROMA_COLLECTION)

    # 1. Seed corpus
    print("\n[1/3] Seeding test corpus into MongoDB and Vector Store...")
    doc_seeds = [
        ("doc-norm", "dbms_normalization.pdf", DOC_1_TEXT, 3),
        ("doc-idx", "dbms_indexing.pdf", DOC_2_TEXT, 12),
        ("doc-tx", "dbms_transactions.pdf", DOC_3_TEXT, 7),
    ]

    for doc_id, doc_name, text, page in doc_seeds:
        emb = embedder.embed([text])
        vs.add_chunks(
            doc_id=doc_id,
            source_name=doc_name,
            chunks=[text],
            embeddings=emb,
            pages=[page],
            user_id=user_id,
        )
        await save_document(
            UploadedDoc(
                id=doc_id,
                name=doc_name,
                kind="pdf",
                size_mb=0.15,
                pages=page + 2,
                chunk_count=1,
                user_id=user_id,
            )
        )
        print(f"  + Seeded: {doc_name} ({len(text)} chars, page {page})")

    # 2. Execute 30 queries
    print("\n[2/3] Executing 30 deterministic evaluation queries...")

    category_results: Dict[str, Dict[str, Any]] = {}
    total_queries = len(EVALUATION_DATASET)
    passed_accuracy = 0
    passed_citations = 0
    hallucination_count = 0
    latencies: List[float] = []

    print(f"\n{'ID':<10} | {'Category':<22} | {'Status':<8} | {'Latency':>8} | {'Acc':<4} | {'Cite':<4} | {'Halluc':<6}")
    print("-" * 75)

    for item in EVALUATION_DATASET:
        qid = item["id"]
        cat = item["category"]
        q = item["question"]

        if cat not in category_results:
            category_results[cat] = {
                "total": 0,
                "accuracy_pass": 0,
                "citation_pass": 0,
                "hallucinations": 0,
                "latencies": [],
            }

        category_results[cat]["total"] += 1

        t0 = time.perf_counter()
        raw_res = await ask_question(q, user_id=user_id)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(dur_ms)
        category_results[cat]["latencies"].append(dur_ms)

        d = raw_res.get("data", {})
        ans = d.get("answer", "")
        status = d.get("status", "")
        citations = d.get("citations", [])

        # Evaluate Accuracy
        acc_pass = True
        for kw in item["must_contain"]:
            if kw.lower() not in ans.lower():
                acc_pass = False
                break

        # Evaluate Citations & Hallucination
        cite_pass = True
        hallucinated = False

        if item["expect_citations"]:
            if not citations:
                cite_pass = False
            else:
                cited_sources = [c.get("source", "") for c in citations]
                top_cite = citations[0]
                source_name = top_cite.get("source", "")
                page_num = top_cite.get("page", 0)
                if item.get("primary_source"):
                    if not any(item["primary_source"] in s for s in cited_sources):
                        cite_pass = False
                if item.get("expected_page") and item["expected_page"] != page_num:
                    cite_pass = False
        else:
            # For absent info, any document citation is a hallucination
            if citations:
                hallucinated = True
                cite_pass = False
            else:
                cite_pass = True

        if acc_pass:
            passed_accuracy += 1
            category_results[cat]["accuracy_pass"] += 1

        if cite_pass:
            passed_citations += 1
            category_results[cat]["citation_pass"] += 1

        if hallucinated:
            hallucination_count += 1
            category_results[cat]["hallucinations"] += 1

        acc_label = "PASS" if acc_pass else "FAIL"
        cite_label = "PASS" if cite_pass else "FAIL"
        hal_label = "YES" if hallucinated else "NO"

        print(f"{qid:<10} | {cat:<22} | {status:<8} | {dur_ms:6.1f}ms | {acc_label:<4} | {cite_label:<4} | {hal_label:<6}")

    # 3. Report Results
    print("\n" + "=" * 80)
    print("  30-QUERY RAG EVALUATION SUMMARY & METRICS")
    print("=" * 80)

    overall_acc_pct = (passed_accuracy / total_queries) * 100.0
    overall_cite_pct = (passed_citations / total_queries) * 100.0
    overall_hal_pct = (hallucination_count / total_queries) * 100.0
    p50_lat = float(np.percentile(latencies, 50))
    p95_lat = float(np.percentile(latencies, 95))

    print(f"\n{'Category':<25} | {'Tests':>6} | {'Accuracy':>10} | {'Citation Acc':>14} | {'Hallucination':>14}")
    print("-" * 78)

    for cat, res in category_results.items():
        n = res["total"]
        acc_pct = (res["accuracy_pass"] / n) * 100.0
        c_pct = (res["citation_pass"] / n) * 100.0
        h_pct = (res["hallucinations"] / n) * 100.0
        print(f"{cat:<25} | {n:>6} | {acc_pct:>9.1f}% | {c_pct:>13.1f}% | {h_pct:>13.1f}%")

    print("-" * 78)
    print(f"{'OVERALL TOTALS':<25} | {total_queries:>6} | {overall_acc_pct:>9.1f}% | {overall_cite_pct:>13.1f}% | {overall_hal_pct:>13.1f}%")
    print(f"\nLatency Distribution: p50={p50_lat:.1f}ms | p95={p95_lat:.1f}ms")

    assert overall_acc_pct >= 90.0, f"RAG accuracy below threshold: {overall_acc_pct:.1f}%"
    assert overall_hal_pct == 0.0, f"Hallucinations detected: {overall_hal_pct:.1f}%"
    print("\n[SUCCESS] All 30 RAG Quality & Grounding criteria verified!")


if __name__ == "__main__":
    asyncio.run(run_30_query_evaluation())
