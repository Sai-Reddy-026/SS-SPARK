"""
services/chat_service.py

Hybrid RAG + General-Chat orchestration for the /api/chat endpoint.

Performance & Reliability Enhancements:
  - Gemini Primary -> NVIDIA Fallback LLM Router
  - Zero-LLM Fast Local Deterministic Heuristic (<1ms routing & contextualization)
  - Hard First-Token Timeout (3.5s) on stream reads
  - Non-blocking vector retrieval with detailed milestone telemetry
  - Structured request correlation logging: [CHAT {req_id}]
  - Multi-tenant isolation and user session management
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger("ss_spark.chat_service")

# Short-lived document cache: avoids a DB round-trip on every message
_doc_cache: Dict[str, tuple[float, Any]] = {}  # user_id → (timestamp, docs)
_DOC_CACHE_TTL = 10.0  # seconds


async def _get_cached_documents(user_id: Optional[str], models_mod: Any) -> List[Any]:
    key = user_id or "__guest__"
    now = time.monotonic()
    if key in _doc_cache:
        ts, docs = _doc_cache[key]
        if now - ts < _DOC_CACHE_TTL:
            return docs
    docs = await models_mod.get_documents(user_id=user_id)
    _doc_cache[key] = (now, docs)
    return docs


def invalidate_doc_cache(user_id: Optional[str] = None) -> None:
    """Call this after an upload or delete so the next request refreshes."""
    key = user_id or "__guest__"
    _doc_cache.pop(key, None)


async def ask_question(
    question: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Hybrid RAG + General-Chat pipeline with full multi-turn conversational memory (Non-streaming).
    """
    from rag.paperqa_connector import get_indexed_paths
    from rag.general_llm import general_chat, is_question_relevant_to_docs, contextualize_query
    from rag.retriever import retrieve as qdrant_retrieve
    from database import models
    from core.config import get_settings

    req_id = f"CHAT-{uuid.uuid4().hex[:6]}"
    t_start = time.perf_counter()
    sid = session_id or str(uuid.uuid4())

    logger.info("[%s] request_start | session=%s | user=%s | q_len=%d", req_id, sid[:8], user_id or "anon", len(question))

    # 0. Retrieve conversation history
    t0 = time.perf_counter()
    prior_messages = await models.get_history(session_id=sid, limit=16, user_id=user_id)
    chat_history: List[Dict[str, str]] = [
        {"role": msg.role, "content": msg.content}
        for msg in prior_messages
        if msg.role in ("user", "assistant") and msg.content
    ]
    hist_ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info("[%s] history_complete in %.2fms (%d messages)", req_id, hist_ms, len(chat_history))

    # 1. Persist user message
    user_msg = models.ChatMessage(
        session_id=sid,
        role="user",
        content=question,
        user_id=user_id,
    )
    await models.save_message(user_msg)

    # 2. Route: Check uploaded documents
    user_docs = await _get_cached_documents(user_id, models)
    pqa_paths = get_indexed_paths(user_id=user_id)
    doc_names = list(
        {d.name for d in user_docs if d.name}.union(
            {p.split("/")[-1].split("\\")[-1] for p in pqa_paths if p}
        )
    )

    pqa_result: Optional[Dict[str, Any]] = None
    citations: List[Dict[str, Any]] = []

    if not doc_names:
        # No documents -> Pure general AI
        logger.info("[%s] routing_complete in 0.00ms | use_rag=False | reason='no_docs'", req_id)
        pqa_result = await general_chat(
            question=question,
            chat_history=chat_history,
            req_id=req_id,
        )

    else:
        # Documents exist -> Fast local heuristic routing (<1ms)
        t_route = time.perf_counter()
        use_rag = is_question_relevant_to_docs(question, doc_names, chat_history=chat_history, req_id=req_id)
        search_query = contextualize_query(question, chat_history=chat_history, req_id=req_id)
        route_ms = round((time.perf_counter() - t_route) * 1000, 2)
        logger.info("[%s] routing_complete in %.2fms | use_rag=%s | search_query=%r", req_id, route_ms, use_rag, search_query[:60])

        if use_rag:
            # RAG Path: Vector retrieval
            retrieved_chunks = []
            try:
                from rag.vector_store import get_vector_store
                cfg = get_settings()
                vs = get_vector_store(str(cfg.CHROMA_DIR), cfg.CHROMA_COLLECTION)
                if vs.count() > 0:
                    retrieval_res = await qdrant_retrieve(
                        search_query,
                        n_results=cfg.TOP_K_RESULTS,
                        user_id=user_id,
                    )
                    retrieved_chunks = retrieval_res.chunks
            except Exception as exc:
                logger.warning("[%s] vector retrieval failed (non-fatal): %s", req_id, exc)

            valid_chunks = [c for c in retrieved_chunks if c.relevance >= 0.25]
            if valid_chunks:
                logger.info("[%s] grounded prompt with %d vector chunks", req_id, len(valid_chunks))
                context_text = "\n\n".join(
                    f"--- Source: {c.source} (Page {c.page}) ---\n{c.text}"
                    for c in valid_chunks
                )
                grounded_prompt = (
                    "You are SS SPARK AI — an expert academic assistant.\n"
                    "Answer the user's question thoroughly and accurately based on the provided document excerpts.\n"
                    "If the answer is found in the context, cite the source name and page number.\n\n"
                    f"CONTEXT FROM UPLOADED DOCUMENTS:\n{context_text}"
                )
                grounded_res = await general_chat(
                    question=question,
                    chat_history=chat_history,
                    system_prompt=grounded_prompt,
                    req_id=req_id,
                )
                if grounded_res.get("answer") and grounded_res.get("status") != "error":
                    pqa_result = dict(grounded_res)
                    pqa_result["status"] = "success"
                    citations = [
                        {
                            "id": c.id or str(uuid.uuid4()),
                            "doc_id": c.doc_id,
                            "source": c.source,
                            "page": c.page,
                            "snippet": c.text[:400],
                            "relevance": round(c.relevance, 4),
                        }
                        for c in valid_chunks
                    ]

            # Fast fallback if no direct chunks
            if pqa_result is None or not citations:
                pqa_result = await general_chat(
                    question=question,
                    chat_history=chat_history,
                    req_id=req_id,
                )

        else:
            # Unrelated to documents -> Pure general AI
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
                req_id=req_id,
            )

    # 4. Extract common fields
    primary_source = citations[0]["source"] if citations else "N/A"
    primary_page = citations[0]["page"] if citations else 0
    confidence = pqa_result.get("confidence", None) if pqa_result else None
    answer_text = pqa_result.get("answer", "") if pqa_result else ""

    # 5. Persist assistant message
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

    # Upsert ChatSession
    if user_id:
        try:
            from database import models as _m
            from datetime import datetime, timezone
            existing_sess = await _m.get_session_by_id(sid, user_id=user_id)
            if not existing_sess:
                clean_title = question.strip().replace("\n", " ")
                if len(clean_title) > 40:
                    clean_title = clean_title[:37] + "..."
                new_sess = _m.ChatSession(
                    id=sid,
                    user_id=user_id,
                    title=clean_title or "New Chat",
                    message_count=2,
                )
                await _m.create_session(new_sess)
            else:
                await _m.update_session(
                    sid,
                    {
                        "message_count": (existing_sess.message_count or 0) + 2,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    user_id=user_id,
                )
        except Exception as sess_err:
            logger.warning("[%s] Session upsert failed (non-fatal): %s", req_id, sess_err)

    total_ms = round((time.perf_counter() - t_start) * 1000, 2)
    logger.info("[%s] total_duration %.2fms", req_id, total_ms)

    return {
        "success": True,
        "data": {
            "answer": answer_text,
            "source": primary_source,
            "page": primary_page,
            "confidence": round(confidence, 4) if confidence is not None else None,
            "citations": citations,
            "references": pqa_result.get("references", "") if pqa_result else "",
            "session_id": sid,
            "cost": pqa_result.get("cost", 0.0) if pqa_result else 0.0,
            "status": pqa_result.get("status", "unknown") if pqa_result else "error",
        },
        "message": "Answer generated successfully",
    }


async def ask_question_stream(
    question: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming version of ask_question().

    Yields Server-Sent Event strings:
        data: {"type": "session", "session_id": "..."}\n\n
        data: {"type": "phase",   "phase": "routing|retrieving|generating"}\n\n
        data: {"type": "token",   "content": "..."}\n\n
        data: {"type": "reset"}\n\n
        data: {"type": "meta",    ...}\n\n
        data: {"type": "done"}\n\n
        data: {"type": "error",   "content": "..."}\n\n
    """
    from rag.general_llm import (
        general_chat_stream,
        is_question_relevant_to_docs,
        contextualize_query,
    )
    from rag.paperqa_connector import get_indexed_paths
    from rag.retriever import retrieve as qdrant_retrieve
    from database import models
    from core.config import get_settings

    req_id = f"CHAT-{uuid.uuid4().hex[:6]}"
    t_start = time.perf_counter()
    sid = session_id or str(uuid.uuid4())

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    try:
        logger.info("[%s] request_start | session=%s | user=%s | q_len=%d", req_id, sid[:8], user_id or "anon", len(question))

        # 0. History
        t0 = time.perf_counter()
        prior_messages = await models.get_history(session_id=sid, limit=16, user_id=user_id)
        chat_history: List[Dict[str, str]] = [
            {"role": msg.role, "content": msg.content}
            for msg in prior_messages
            if msg.role in ("user", "assistant") and msg.content
        ]
        hist_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info("[%s] history_complete in %.2fms (%d messages)", req_id, hist_ms, len(chat_history))

        # 1. Persist user message
        user_msg = models.ChatMessage(
            session_id=sid,
            role="user",
            content=question,
            user_id=user_id,
        )
        await models.save_message(user_msg)

        # Emit session_id immediately so frontend can lock in conversation ID
        yield _sse({"type": "session", "session_id": sid})

        # 2. Route: Check uploaded documents
        user_docs = await _get_cached_documents(user_id, models)
        pqa_paths = get_indexed_paths(user_id=user_id)
        doc_names = list(
            {d.name for d in user_docs if d.name}.union(
                {p.split("/")[-1].split("\\")[-1] for p in pqa_paths if p}
            )
        )

        answer_text = ""
        citations: List[Dict[str, Any]] = []
        status = "general"
        confidence = None

        if not doc_names:
            # No documents -> stream general AI answer immediately
            logger.info("[%s] routing_complete in 0.00ms | use_rag=False | reason='no_docs'", req_id)
            yield _sse({"type": "phase", "phase": "generating"})
            system_prompt = (
                "You are SS SPARK AI — an advanced, intelligent, and helpful conversational AI "
                "assistant like ChatGPT, Claude, and Gemini.\n"
                "- Maintain continuous context across the conversation and follow-up questions.\n"
                "- Answer thoroughly, accurately, and naturally based on the conversation so far.\n"
                "- Format code with syntax-highlighted Markdown code blocks.\n"
                "- Never fabricate false citations. If unsure, say so clearly."
            )
            async for chunk in general_chat_stream(
                question, system_prompt=system_prompt, chat_history=chat_history, req_id=req_id
            ):
                event_type, payload = chunk if isinstance(chunk, tuple) else ("token", chunk)
                if event_type == "reset":
                    answer_text = ""
                    yield _sse({"type": "reset"})
                elif event_type == "token":
                    answer_text += payload
                    yield _sse({"type": "token", "content": payload})

        else:
            # Documents exist -> fast local deterministic heuristic (<1ms)
            t_route = time.perf_counter()
            use_rag = is_question_relevant_to_docs(question, doc_names, chat_history=chat_history, req_id=req_id)
            search_query = contextualize_query(question, chat_history=chat_history, req_id=req_id)
            route_ms = round((time.perf_counter() - t_route) * 1000, 2)
            logger.info("[%s] routing_complete in %.2fms | use_rag=%s | search_query=%r", req_id, route_ms, use_rag, search_query[:60])

            if use_rag:
                # RAG path: retrieve chunks, then stream grounded answer
                yield _sse({"type": "phase", "phase": "retrieving"})
                retrieved_chunks = []
                try:
                    from rag.vector_store import get_vector_store
                    cfg = get_settings()
                    vs = get_vector_store(str(cfg.CHROMA_DIR), cfg.CHROMA_COLLECTION)
                    if vs.count() > 0:
                        retrieval_res = await qdrant_retrieve(
                            search_query,
                            n_results=cfg.TOP_K_RESULTS,
                            user_id=user_id,
                            req_id=req_id,
                        )
                        retrieved_chunks = retrieval_res.chunks
                except Exception as exc:
                    logger.warning("[%s] Vector retrieval error: %s", req_id, exc)

                valid_chunks = [c for c in retrieved_chunks if c.relevance >= 0.25]
                yield _sse({"type": "phase", "phase": "generating"})

                if valid_chunks:
                    status = "success"
                    citations = [
                        {
                            "id": c.id or str(uuid.uuid4()),
                            "doc_id": c.doc_id,
                            "source": c.source,
                            "page": c.page,
                            "snippet": c.text[:400],
                            "relevance": round(c.relevance, 4),
                        }
                        for c in valid_chunks
                    ]
                    context_text = "\n\n".join(
                        f"--- Source: {c.source} (Page {c.page}) ---\n{c.text}"
                        for c in valid_chunks
                    )
                    grounded_prompt = (
                        "You are SS SPARK AI — an expert academic assistant.\n"
                        "Answer the user's question thoroughly and accurately based on the provided document excerpts.\n"
                        "If the answer is found in the context, cite the source name and page number.\n\n"
                        f"CONTEXT FROM UPLOADED DOCUMENTS:\n{context_text}"
                    )
                    async for chunk in general_chat_stream(
                        question, system_prompt=grounded_prompt, chat_history=chat_history, req_id=req_id
                    ):
                        event_type, payload = chunk if isinstance(chunk, tuple) else ("token", chunk)
                        if event_type == "reset":
                            answer_text = ""
                            yield _sse({"type": "reset"})
                        elif event_type == "token":
                            answer_text += payload
                            yield _sse({"type": "token", "content": payload})

                else:
                    # No strong vector chunks -> stream conversational answer
                    async for chunk in general_chat_stream(
                        question, chat_history=chat_history, req_id=req_id
                    ):
                        event_type, payload = chunk if isinstance(chunk, tuple) else ("token", chunk)
                        if event_type == "reset":
                            answer_text = ""
                            yield _sse({"type": "reset"})
                        elif event_type == "token":
                            answer_text += payload
                            yield _sse({"type": "token", "content": payload})

            else:
                # Unrelated to docs -> stream general answer
                yield _sse({"type": "phase", "phase": "generating"})
                system_prompt = (
                    "You are SS SPARK AI — an advanced, intelligent, conversational assistant like ChatGPT, Claude, and Gemini.\n"
                    "- The user has uploaded documents, but this question is general knowledge, conversational follow-up, or coding help.\n"
                    "- Answer naturally using your general knowledge and the full conversation history.\n"
                    "- Be accurate, thorough, and format code with markdown code blocks.\n"
                    "- Do NOT fabricate or hallucinate citations to the user's uploaded documents."
                )
                async for chunk in general_chat_stream(
                    question, system_prompt=system_prompt, chat_history=chat_history, req_id=req_id
                ):
                    event_type, payload = chunk if isinstance(chunk, tuple) else ("token", chunk)
                    if event_type == "reset":
                        answer_text = ""
                        yield _sse({"type": "reset"})
                    elif event_type == "token":
                        answer_text += payload
                        yield _sse({"type": "token", "content": payload})

        # 5. Persist assistant message
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

        # Upsert ChatSession
        if user_id:
            try:
                from database import models as _m
                from datetime import datetime, timezone
                existing_sess = await _m.get_session_by_id(sid, user_id=user_id)
                if not existing_sess:
                    clean_title = question.strip().replace("\n", " ")
                    if len(clean_title) > 40:
                        clean_title = clean_title[:37] + "..."
                    await _m.create_session(
                        _m.ChatSession(
                            id=sid,
                            user_id=user_id,
                            title=clean_title or "New Chat",
                            message_count=2,
                        )
                    )
                else:
                    await _m.update_session(
                        sid,
                        {
                            "message_count": (existing_sess.message_count or 0) + 2,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        },
                        user_id=user_id,
                    )
            except Exception as sess_err:
                logger.warning("[%s] Session upsert error: %s", req_id, sess_err)

        # 6. Final meta event
        primary_source = citations[0]["source"] if citations else "N/A"
        primary_page = citations[0]["page"] if citations else 0

        yield _sse({
            "type": "meta",
            "session_id": sid,
            "source": primary_source,
            "page": primary_page,
            "confidence": round(confidence, 4) if confidence is not None else None,
            "citations": citations,
            "references": "",
            "status": status,
            "cost": 0.0,
        })

        total_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.info("[%s] total_duration %.2fms | total_chars=%d", req_id, total_ms, len(answer_text))
        yield _sse({"type": "done"})

    except asyncio.CancelledError:
        logger.info("[%s] Client cancelled stream request", req_id)
        raise
    except Exception as exc:
        logger.exception("[%s] Unhandled stream exception: %s", req_id, exc)
        yield _sse({"type": "error", "content": "AI service is temporarily unavailable. Please try again."})
        yield _sse({"type": "done"})
