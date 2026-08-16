"""
services/chat_service.py

Hybrid RAG + General-Chat orchestration for the /api/chat endpoint.

Decision logic
──────────────
                    User sends message
                           │
              Are documents indexed?
                    /         \\
                  NO          YES
                  │             │
                  ▼             ▼
            General AI    is_question_relevant_to_docs()?
              answer        /              \\
                       Relevant          Not relevant
                          │                   │
                          ▼                   ▼
                    RAG (PaperQA          General AI
                    + Qdrant)              answer
                          │                   │
                          └────────┬──────────┘
                                   ▼
                    Persist + return structured JSON

Flow (RAG path):
    1. Persist user message to MongoDB
    2. Call PaperQA connector (agent_query internally)
    3. Map PaperQA AnswerResponse → API response format
    4. Enrich citations with Qdrant vector search (additive — safe if offline)
    5. Persist assistant message to MongoDB
    6. Return structured JSON matching the frontend contract

Flow (General path):
    1. Persist user message to MongoDB
    2. Call general_llm.general_chat() via litellm directly
    3. Return same JSON shape (citations=[], status="general")
    4. Persist assistant message
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def ask_question(
    question: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Hybrid RAG + General-Chat pipeline with full multi-turn conversational memory.

    Returns the standard API contract::

        {
            "success": True,
            "data": {
                "answer":     str,
                "source":     str,      # primary source filename ("N/A" for general)
                "page":       int,      # primary source page (0 for general)
                "confidence": float | None,
                "citations":  [{id, source, page, snippet, relevance}],
                "references": str,      # formatted bibliography (empty for general)
                "session_id": str,
                "cost":       float,
                "status":     str,      # "success"|"partial"|"unsure"|"general"|"error"
            },
            "message": str,
        }
    """
    from rag.paperqa_connector import query as pqa_query, get_indexed_count, get_indexed_paths
    from rag.general_llm import general_chat, is_question_relevant_to_docs, contextualize_query
    from rag.retriever import retrieve as qdrant_retrieve
    from database import models
    from core.config import get_settings

    sid = session_id or str(uuid.uuid4())

    # ------------------------------------------------------------------ #
    # 0. Retrieve conversation history for multi-turn context memory
    # ------------------------------------------------------------------ #
    prior_messages = await models.get_history(session_id=sid, limit=16, user_id=user_id)
    chat_history: List[Dict[str, str]] = [
        {"role": msg.role, "content": msg.content}
        for msg in prior_messages
        if msg.role in ("user", "assistant") and msg.content
    ]

    # ------------------------------------------------------------------ #
    # 1. Persist user message
    # ------------------------------------------------------------------ #
    user_msg = models.ChatMessage(
        session_id=sid,
        role="user",
        content=question,
        user_id=user_id,
    )
    await models.save_message(user_msg)

    # ------------------------------------------------------------------ #
    # 2. Route: no documents → straight to general LLM with full chat history
    # ------------------------------------------------------------------ #
    docs_count = get_indexed_count()

    if docs_count == 0:
        logger.info(
            "No documents indexed — routing question to general LLM (history turns=%d): %s",
            len(chat_history),
            question[:80],
        )
        pqa_result = await general_chat(
            question=question,
            chat_history=chat_history,
            system_prompt=(
                "You are SS SPARK AI — an advanced, intelligent, and helpful conversational AI "
                "assistant like ChatGPT, Claude, and Gemini.\n"
                "- Maintain continuous context across the conversation and follow-up questions.\n"
                "- Answer thoroughly, accurately, and naturally based on the conversation so far.\n"
                "- Format code with syntax-highlighted Markdown code blocks.\n"
                "- Never fabricate false citations. If unsure, say so clearly."
            ),
        )
        citations: List[Dict[str, Any]] = []

    else:
        # -------------------------------------------------------------- #
        # 3. Documents exist — classify relevance with conversation context
        # -------------------------------------------------------------- #
        doc_names = [
            p.split("/")[-1].split("\\")[-1]   # basename only
            for p in get_indexed_paths()
        ]

        use_rag = await is_question_relevant_to_docs(
            question,
            doc_names,
            chat_history=chat_history,
        )

        if use_rag:
            # Contextualize query for document retrieval in case it's a follow-up
            search_query = await contextualize_query(question, chat_history=chat_history)
            logger.info(
                "Documents relevant — routing to RAG pipeline with query=%r: %s",
                search_query[:80],
                question[:80],
            )
            # ---------------------------------------------------------- #
            # 3a. RAG path: Direct Qdrant/ChromaDB retrieval + PaperQA
            # ---------------------------------------------------------- #
            retrieved_chunks = []
            try:
                from rag.vector_store import get_vector_store
                cfg = get_settings()
                vs = get_vector_store(str(cfg.CHROMA_DIR), cfg.CHROMA_COLLECTION)
                if vs.count() > 0:
                    retrieval_res = qdrant_retrieve(
                        search_query,
                        n_results=cfg.TOP_K_RESULTS,
                        user_id=user_id,
                    )
                    retrieved_chunks = retrieval_res.chunks
            except Exception as exc:
                logger.warning("Vector store retrieval failed (non-fatal): %s", exc)

            # Try PaperQA agentic query first
            pqa_result = await pqa_query(search_query)

            # Map PaperQA sources → citations
            citations = [
                {
                    "id": str(uuid.uuid4()),
                    "source": s["source"],
                    "page": s["page"],
                    "snippet": s["snippet"],
                    "relevance": s["relevance"],
                }
                for s in pqa_result.get("sources", [])
            ]

            # If PaperQA had no sources or returned unsure, use the retrieved chunks with General LLM
            if (not citations or pqa_result.get("status") in ("unsure", "error")) and retrieved_chunks:
                logger.info("Answering directly from %d retrieved vector chunks", len(retrieved_chunks))
                context_text = "\n\n".join(
                    f"--- Source: {c.source} (Page {c.page}) ---\n{c.text}"
                    for c in retrieved_chunks
                )
                grounded_prompt = (
                    "You are SS SPARK AI — an expert academic assistant.\n"
                    "Answer the user's question accurately and thoroughly based on the provided document excerpts.\n"
                    "If the answer is found in the context, cite the source name and page number.\n\n"
                    f"CONTEXT FROM UPLOADED DOCUMENTS:\n{context_text}"
                )
                grounded_res = await general_chat(
                    question=question,
                    chat_history=chat_history,
                    system_prompt=grounded_prompt,
                )
                if grounded_res.get("answer") and grounded_res.get("status") != "error":
                    pqa_result = grounded_res
                    citations = [
                        {
                            "id": str(uuid.uuid4()),
                            "source": c.source,
                            "page": c.page,
                            "snippet": c.text[:400],
                            "relevance": round(c.relevance, 4),
                        }
                        for c in retrieved_chunks
                    ]
            elif (not citations or pqa_result.get("status") in ("unsure", "error")) and chat_history:
                logger.info("RAG returned unsure/no citations for follow-up — answering with conversation context")
                general_fallback = await general_chat(
                    question=question,
                    chat_history=chat_history,
                )
                if general_fallback.get("answer") and general_fallback.get("status") != "error":
                    pqa_result = general_fallback
                    citations = []

            # Enrich remaining citations from retrieved chunks
            if citations and retrieved_chunks:
                existing_keys = {(c["source"], c["page"]) for c in citations}
                for chunk in retrieved_chunks:
                    key = (chunk.source, chunk.page)
                    if key not in existing_keys:
                        citations.append(
                            {
                                "id": str(uuid.uuid4()),
                                "source": chunk.source,
                                "page": chunk.page,
                                "snippet": chunk.text[:400],
                                "relevance": round(chunk.relevance, 4),
                            }
                        )
                        existing_keys.add(key)

        else:
            logger.info(
                "Question not relevant to documents — using general LLM (history turns=%d): %s",
                len(chat_history),
                question[:80],
            )
            # ---------------------------------------------------------- #
            # 3b. General-chat path — docs exist but question is unrelated
            # ---------------------------------------------------------- #
            pqa_result = await general_chat(
                question=question,
                chat_history=chat_history,
                system_prompt=(
                    "You are SS SPARK AI — an advanced, intelligent, conversational assistant like ChatGPT, Claude, and Gemini.\n"
                    "- The user has uploaded documents, but this question is general knowledge, conversational follow-up, or coding help.\n"
                    "- Answer naturally using your general knowledge and the full conversation history.\n"
                    "- Be accurate, thorough, and format code with markdown code blocks.\n"
                    "- Do NOT fabricate or hallucinate citations to the user's uploaded documents."
                ),
            )
            citations = []

    # ------------------------------------------------------------------ #
    # 4. Extract common fields
    # ------------------------------------------------------------------ #
    primary_source = citations[0]["source"] if citations else "N/A"
    primary_page = citations[0]["page"] if citations else 0
    confidence = pqa_result.get("confidence", None)
    answer_text = pqa_result.get("answer", "")

    # ------------------------------------------------------------------ #
    # 5. Persist assistant message
    # ------------------------------------------------------------------ #
    citation_models = [
        models.Citation(
            source=c["source"],
            page=c["page"],
            snippet=c["snippet"],
            relevance=c["relevance"],
        )
        for c in citations
    ]
    assistant_msg = models.ChatMessage(
        session_id=sid,
        role="assistant",
        content=answer_text,
        confidence=confidence,
        citations=citation_models,
        user_id=user_id,
    )
    await models.save_message(assistant_msg)

    # ------------------------------------------------------------------ #
    # 5b. Auto-create or update ChatSession so it appears in Recent Chats
    # ------------------------------------------------------------------ #
    if user_id:
        try:
            from database import user_models
            from datetime import datetime, timezone

            existing_sess = await user_models.get_session_by_id(sid)
            if not existing_sess:
                clean_title = question.strip().replace("\n", " ")
                if len(clean_title) > 40:
                    clean_title = clean_title[:37] + "..."
                new_sess = user_models.ChatSession(
                    id=sid,
                    user_id=user_id,
                    title=clean_title or "New Chat",
                    message_count=2,
                )
                await user_models.create_session(new_sess)
            else:
                await user_models.update_session(
                    sid,
                    {
                        "message_count": (existing_sess.message_count or 0) + 2,
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
        except Exception as sess_err:
            logger.warning("Failed to upsert chat session record (non-fatal): %s", sess_err)


    # ------------------------------------------------------------------ #
    # 6. Return structured response
    # ------------------------------------------------------------------ #
    return {
        "success": True,
        "data": {
            "answer": answer_text,
            "source": primary_source,
            "page": primary_page,
            "confidence": round(confidence, 4) if confidence is not None else None,
            "citations": citations,
            "references": pqa_result.get("references", ""),
            "session_id": sid,
            "cost": pqa_result.get("cost", 0.0),
            "status": pqa_result.get("status", "unknown"),
        },
        "message": "Answer generated successfully",
    }
