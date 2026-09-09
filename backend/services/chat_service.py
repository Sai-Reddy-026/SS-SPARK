"""
services/chat_service.py

Hybrid RAG + Question Paper Intelligence + General-Chat orchestration for the /api/chat endpoint.

Key Capabilities:
  - Multimodal Vision Answering for uploaded / attached question papers & screenshots
  - Question Paper Intelligence: Auto-detection of question numbers ("Question 2", "Q5", "Problem 3") and paper-wide solving ("Solve all")
  - Structured sidecar question locator & high-precision vector chunk retrieval
  - LaTeX mathematical formula preservation ($...$ inline, $$...$$ display)
  - MCQ option analysis and diagram/circuit description awareness
  - Multi-phase SSE streaming: reading_paper -> locating_question -> retrieving -> generating
  - Strict multi-tenant isolation and user session management
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

logger = logging.getLogger("ss_spark.chat_service")

# Short-lived document cache: avoids a DB round-trip on every message
_doc_cache: Dict[str, tuple[float, Any]] = {}  # user_id → (timestamp, docs)
_DOC_CACHE_TTL = 10.0  # seconds


ACADEMIC_SOLVER_PROMPT = (
    "You are SS SPARK AI — an expert academic assistant, professor, and examination question solver.\n"
    "Your task is to provide clear, rigorous, and highly detailed answers/solutions to academic questions.\n\n"
    "CRITICAL GUIDELINES:\n"
    "1. STEP-BY-STEP WORKING: Provide full derivations, step-by-step reasoning, calculations, or proofs without skipping intermediate steps.\n"
    "2. LATEX FORMULAS: Format ALL mathematical, scientific, and chemical expressions strictly in LaTeX. Use `$formula$` for inline math and `$$formula$$` for standalone equation blocks. Never use plain text approximations for fractions, square roots, integrals, matrices, or Greek symbols.\n"
    "3. MULTIPLE CHOICE QUESTIONS (MCQs): If the question has options (A, B, C, D):\n"
    "   - Clearly declare the correct option at the top (e.g., '**Correct Option: (B)**').\n"
    "   - Provide the complete step-by-step justification for why that option is correct.\n"
    "   - Clearly explain why the other options are incorrect.\n"
    "4. DIAGRAMS & FIGURES: If the question involves a diagram, circuit, graph, or chart, describe the key visual elements and directly integrate them into your solution.\n"
    "5. SECTION & MARKS AWARENESS: Adapt the depth and length of your solution to the marks and section indicated (e.g., concise for 1-2 mark questions, comprehensive and thorough for 5-10 mark questions).\n"
    "6. CITATION: Cite the document name and page/question number clearly where relevant."
)


def detect_target_question(text: str) -> Optional[int]:
    """Extract question number from queries like 'Question 2', 'Q5', 'Problem 3', 'Solve 4'."""
    pattern = r"(?:question|q|problem|no\.?|ques\.?|que\.?)\s*#?\s*(\d+)"
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    m2 = re.search(r"\b(?:solve|answer|explain)\s+(\d+)\b", text, re.IGNORECASE)
    if m2:
        try:
            return int(m2.group(1))
        except ValueError:
            pass
    return None


def is_solve_all_or_paper_request(text: str) -> bool:
    """Check if query is asking to solve the whole paper or all questions."""
    t = text.lower()
    return any(p in t for p in [
        "solve all", "answer all", "all questions", "solve this", "solve the paper",
        "solve paper", "answer this", "solve the questions", "solution for all",
        "what are the questions", "list the questions"
    ])


def load_question_from_doc_sidecars(doc_file_path: str, target_q: Optional[int], is_solve_all: bool) -> Optional[Dict[str, Any]]:
    """Look up question(s) from document's _questions.json sidecar."""
    if not doc_file_path:
        return None
    p = Path(doc_file_path)
    q_file = p.with_name(f"{p.stem}_questions.json")
    if not q_file.exists():
        return None
    try:
        data = json.loads(q_file.read_text(encoding="utf-8"))
        questions = data.get("questions", [])
        if is_solve_all:
            return {
                "title": data.get("title", ""),
                "sections": data.get("sections", []),
                "questions": questions,
                "all": True,
            }
        if target_q is not None:
            for idx, q in enumerate(questions):
                raw_qnum = str(q.get("q_num", "")).strip()
                num_match = re.search(r"\d+", raw_qnum)
                if num_match and int(num_match.group(0)) == target_q:
                    return {"question": q, "title": data.get("title", "")}
                if idx + 1 == target_q:
                    return {"question": q, "title": data.get("title", "")}
    except Exception as err:
        logger.debug("Error reading question sidecar %s: %s", q_file, err)
    return None


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
    attachment: Optional[Dict[str, Any]] = None,
    doc_id: Optional[str] = None,
    image_data: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Hybrid RAG + Question Paper Intelligence + General-Chat pipeline (Non-streaming).
    """
    from rag.paperqa_connector import get_indexed_paths
    from rag.general_llm import general_chat, is_question_relevant_to_docs, contextualize_query
    from rag.retriever import retrieve as qdrant_retrieve
    from database import models
    from core.config import get_settings

    req_id = f"CHAT-{uuid.uuid4().hex[:6]}"
    t_start = time.perf_counter()
    sid = session_id or str(uuid.uuid4())

    logger.info(
        "[%s] request_start | session=%s | user=%s | q_len=%d | has_attachment=%s",
        req_id,
        sid[:8],
        user_id or "anon",
        len(question),
        bool(attachment or image_data),
    )

    # 0. Retrieve conversation history
    prior_messages = await models.get_history(session_id=sid, limit=16, user_id=user_id)
    chat_history: List[Dict[str, str]] = [
        {"role": msg.role, "content": msg.content}
        for msg in prior_messages
        if msg.role in ("user", "assistant") and msg.content
    ]

    # 1. Persist user message
    user_msg = models.ChatMessage(
        session_id=sid,
        role="user",
        content=question,
        attachment=attachment,
        user_id=user_id,
    )
    await models.save_message(user_msg)

    # 2. Check for direct image attachment or image data
    active_image = image_data or (attachment.get("data_url") or attachment.get("path") if attachment else None)
    target_q = detect_target_question(question)
    is_all = is_solve_all_or_paper_request(question)

    pqa_result: Optional[Dict[str, Any]] = None
    citations: List[Dict[str, Any]] = []

    if active_image:
        # User attached an image directly in this request
        att_name = attachment.get("name", "Attached Image") if attachment else "Attached Image"
        multimodal_prompt = (
            f"{ACADEMIC_SOLVER_PROMPT}\n\n"
            f"The user has attached an image of a question paper, diagram, or study material: '{att_name}'.\n"
            "Carefully examine the image to locate questions, equations, diagrams, and options."
        )
        if target_q is not None:
            multimodal_prompt += f"\nLocate Question {target_q} on the paper, quote its text, and provide the complete step-by-step solution."
        elif is_all:
            multimodal_prompt += "\nSolve all questions found on this paper in order, numbering each solution clearly."

        pqa_result = await general_chat(
            question=question,
            system_prompt=multimodal_prompt,
            chat_history=chat_history,
            image_data=active_image,
            req_id=req_id,
        )
        citations = [
            {
                "id": str(uuid.uuid4()),
                "doc_id": doc_id or "",
                "source": att_name,
                "page": 1,
                "snippet": f"Analyzed directly from attached image: {att_name}",
                "relevance": 1.0,
            }
        ]

    else:
        # 3. Check user uploaded documents
        user_docs = await _get_cached_documents(user_id, models)
        pqa_paths = get_indexed_paths(user_id=user_id)
        doc_names = list(
            {d.name for d in user_docs if d.name}.union(
                {p.split("/")[-1].split("\\")[-1] for p in pqa_paths if p}
            )
        )

        # Check if query requests a specific question from uploaded paper sidecars
        found_sidecar_info: Optional[Tuple[Any, Dict[str, Any]]] = None
        if user_docs and (target_q is not None or is_all):
            for doc in user_docs:
                fpath = getattr(doc, "file_path", "")
                q_info = load_question_from_doc_sidecars(fpath, target_q, is_all)
                if q_info:
                    found_sidecar_info = (doc, q_info)
                    break

        if found_sidecar_info:
            doc, q_info = found_sidecar_info
            context_text = f"DOCUMENT: {doc.name}\n"
            if "question" in q_info:
                q_item = q_info["question"]
                context_text += (
                    f"QUESTION NUMBER: {q_item.get('q_num')}\n"
                    f"SECTION: {q_item.get('section', 'General')}\n"
                    f"MARKS: {q_item.get('marks', 'N/A')}\n"
                    f"QUESTION TEXT:\n{q_item.get('text')}\n"
                )
                if q_item.get("options"):
                    context_text += "OPTIONS:\n" + "\n".join(f"  {opt}" for opt in q_item["options"]) + "\n"
                if q_item.get("has_diagram") and q_item.get("diagram_description"):
                    context_text += f"DIAGRAM / FIGURE:\n{q_item['diagram_description']}\n"
            elif "questions" in q_info:
                context_text += f"EXAM TITLE: {q_info.get('title', '')}\nALL QUESTIONS:\n"
                for q_item in q_info["questions"]:
                    opt_str = ("\n   Options: " + " | ".join(q_item.get("options", []))) if q_item.get("options") else ""
                    context_text += f"[{q_item.get('section', '')}] {q_item.get('q_num')}: {q_item.get('text')}{opt_str} ({q_item.get('marks', '')})\n"

            doc_img_path = getattr(doc, "file_path", "")
            img_to_pass = doc_img_path if doc_img_path and Path(doc_img_path).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else None

            grounded_prompt = (
                f"{ACADEMIC_SOLVER_PROMPT}\n\n"
                f"CONTEXT EXTRACTED FROM UPLOADED QUESTION PAPER:\n{context_text}"
            )
            pqa_result = await general_chat(
                question=question,
                system_prompt=grounded_prompt,
                chat_history=chat_history,
                image_data=img_to_pass,
                req_id=req_id,
            )
            citations = [
                {
                    "id": str(uuid.uuid4()),
                    "doc_id": doc.id,
                    "source": doc.name,
                    "page": 1,
                    "snippet": context_text[:400],
                    "relevance": 1.0,
                }
            ]

        elif not doc_names:
            # Pure general AI
            pqa_result = await general_chat(
                question=question,
                chat_history=chat_history,
                req_id=req_id,
            )

        else:
            # Vector RAG Path
            use_rag = is_question_relevant_to_docs(question, doc_names, chat_history=chat_history, req_id=req_id)
            search_query = contextualize_query(question, chat_history=chat_history, req_id=req_id)

            if use_rag:
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
                    # Prioritize question number match if target_q is set
                    if target_q is not None:
                        valid_chunks.sort(
                            key=lambda c: 0 if (getattr(c, "question_number", None) == target_q or f"question {target_q}" in c.text.lower()) else 1
                        )

                    context_text = "\n\n".join(
                        f"--- Source: {c.source} (Page {c.page}) ---\n{c.text}"
                        for c in valid_chunks
                    )
                    grounded_prompt = (
                        f"{ACADEMIC_SOLVER_PROMPT}\n\n"
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

                if pqa_result is None or not citations:
                    pqa_result = await general_chat(
                        question=question,
                        chat_history=chat_history,
                        req_id=req_id,
                    )

            else:
                pqa_result = await general_chat(
                    question=question,
                    chat_history=chat_history,
                    system_prompt=(
                        "You are SS SPARK AI — an advanced, intelligent, conversational assistant.\n"
                        "- Answer naturally using your general knowledge and the full conversation history.\n"
                        "- Be accurate, thorough, and format code or math with appropriate markdown."
                    ),
                    req_id=req_id,
                )

    primary_source = citations[0]["source"] if citations else "N/A"
    primary_page = citations[0]["page"] if citations else 0
    confidence = pqa_result.get("confidence", 0.95) if pqa_result else None
    answer_text = pqa_result.get("answer", "") if pqa_result else ""

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
    attachment: Optional[Dict[str, Any]] = None,
    doc_id: Optional[str] = None,
    image_data: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming version of ask_question() with multi-phase SSE emissions.

    Yields Server-Sent Event strings:
        data: {"type": "session", "session_id": "..."}\n\n
        data: {"type": "phase",   "phase": "reading_paper|locating_question|retrieving|generating"}\n\n
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
        logger.info(
            "[%s] stream_start | session=%s | user=%s | q_len=%d | has_attachment=%s",
            req_id,
            sid[:8],
            user_id or "anon",
            len(question),
            bool(attachment or image_data),
        )

        # 0. History
        prior_messages = await models.get_history(session_id=sid, limit=16, user_id=user_id)
        chat_history: List[Dict[str, str]] = [
            {"role": msg.role, "content": msg.content}
            for msg in prior_messages
            if msg.role in ("user", "assistant") and msg.content
        ]

        # 1. Persist user message
        user_msg = models.ChatMessage(
            session_id=sid,
            role="user",
            content=question,
            attachment=attachment,
            user_id=user_id,
        )
        await models.save_message(user_msg)

        # Emit session_id immediately so frontend can lock in conversation ID
        yield _sse({"type": "session", "session_id": sid})

        answer_text = ""
        citations: List[Dict[str, Any]] = []
        status = "general"
        confidence = 0.95

        # 2. Check for direct image attachment or image data
        active_image = image_data or (attachment.get("data_url") or attachment.get("path") if attachment else None)
        target_q = detect_target_question(question)
        is_all = is_solve_all_or_paper_request(question)

        if active_image:
            yield _sse({"type": "phase", "phase": "reading_paper"})
            att_name = attachment.get("name", "Attached Image") if attachment else "Attached Image"
            multimodal_prompt = (
                f"{ACADEMIC_SOLVER_PROMPT}\n\n"
                f"The user has attached an image of a question paper, diagram, or study material: '{att_name}'.\n"
                "Carefully inspect the image to locate questions, equations, diagrams, and options."
            )
            if target_q is not None:
                multimodal_prompt += f"\nLocate Question {target_q} on the paper, quote its text, and provide the complete step-by-step solution."
            elif is_all:
                multimodal_prompt += "\nSolve all questions found on this paper in order, numbering each solution clearly."

            yield _sse({"type": "phase", "phase": "generating"})
            status = "success"
            confidence = 0.98
            citations = [
                {
                    "id": str(uuid.uuid4()),
                    "doc_id": doc_id or "",
                    "source": att_name,
                    "page": 1,
                    "snippet": f"Analyzed directly from attached image: {att_name}",
                    "relevance": 1.0,
                }
            ]

            async for chunk in general_chat_stream(
                question,
                system_prompt=multimodal_prompt,
                chat_history=chat_history,
                image_data=active_image,
                req_id=req_id,
            ):
                event_type, payload = chunk if isinstance(chunk, tuple) else ("token", chunk)
                if event_type == "reset":
                    answer_text = ""
                    yield _sse({"type": "reset"})
                elif event_type == "token":
                    answer_text += payload
                    yield _sse({"type": "token", "content": payload})

        else:
            # 3. Check uploaded documents
            user_docs = await _get_cached_documents(user_id, models)
            pqa_paths = get_indexed_paths(user_id=user_id)
            doc_names = list(
                {d.name for d in user_docs if d.name}.union(
                    {p.split("/")[-1].split("\\")[-1] for p in pqa_paths if p}
                )
            )

            # Check if query requests a specific question from uploaded paper sidecars
            found_sidecar_info: Optional[Tuple[Any, Dict[str, Any]]] = None
            if user_docs and (target_q is not None or is_all):
                for doc in user_docs:
                    fpath = getattr(doc, "file_path", "")
                    q_info = load_question_from_doc_sidecars(fpath, target_q, is_all)
                    if q_info:
                        found_sidecar_info = (doc, q_info)
                        break

            if found_sidecar_info:
                yield _sse({"type": "phase", "phase": "locating_question"})
                doc, q_info = found_sidecar_info
                context_text = f"DOCUMENT: {doc.name}\n"
                if "question" in q_info:
                    q_item = q_info["question"]
                    context_text += (
                        f"QUESTION NUMBER: {q_item.get('q_num')}\n"
                        f"SECTION: {q_item.get('section', 'General')}\n"
                        f"MARKS: {q_item.get('marks', 'N/A')}\n"
                        f"QUESTION TEXT:\n{q_item.get('text')}\n"
                    )
                    if q_item.get("options"):
                        context_text += "OPTIONS:\n" + "\n".join(f"  {opt}" for opt in q_item["options"]) + "\n"
                    if q_item.get("has_diagram") and q_item.get("diagram_description"):
                        context_text += f"DIAGRAM / FIGURE:\n{q_item['diagram_description']}\n"
                elif "questions" in q_info:
                    context_text += f"EXAM TITLE: {q_info.get('title', '')}\nALL QUESTIONS:\n"
                    for q_item in q_info["questions"]:
                        opt_str = ("\n   Options: " + " | ".join(q_item.get("options", []))) if q_item.get("options") else ""
                        context_text += f"[{q_item.get('section', '')}] {q_item.get('q_num')}: {q_item.get('text')}{opt_str} ({q_item.get('marks', '')})\n"

                doc_img_path = getattr(doc, "file_path", "")
                img_to_pass = doc_img_path if doc_img_path and Path(doc_img_path).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else None

                grounded_prompt = (
                    f"{ACADEMIC_SOLVER_PROMPT}\n\n"
                    f"CONTEXT EXTRACTED FROM UPLOADED QUESTION PAPER:\n{context_text}"
                )
                yield _sse({"type": "phase", "phase": "generating"})
                status = "success"
                confidence = 0.97
                citations = [
                    {
                        "id": str(uuid.uuid4()),
                        "doc_id": doc.id,
                        "source": doc.name,
                        "page": 1,
                        "snippet": context_text[:400],
                        "relevance": 1.0,
                    }
                ]

                async for chunk in general_chat_stream(
                    question,
                    system_prompt=grounded_prompt,
                    chat_history=chat_history,
                    image_data=img_to_pass,
                    req_id=req_id,
                ):
                    event_type, payload = chunk if isinstance(chunk, tuple) else ("token", chunk)
                    if event_type == "reset":
                        answer_text = ""
                        yield _sse({"type": "reset"})
                    elif event_type == "token":
                        answer_text += payload
                        yield _sse({"type": "token", "content": payload})

            elif not doc_names:
                # No documents -> pure general chat
                yield _sse({"type": "phase", "phase": "generating"})
                system_prompt = (
                    "You are SS SPARK AI — an advanced, intelligent, and helpful conversational AI assistant.\n"
                    "- Maintain continuous context across the conversation.\n"
                    "- Answer thoroughly, accurately, and naturally.\n"
                    "- Format code or math with appropriate markdown."
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
                # Documents exist -> Vector RAG path
                use_rag = is_question_relevant_to_docs(question, doc_names, chat_history=chat_history, req_id=req_id)
                search_query = contextualize_query(question, chat_history=chat_history, req_id=req_id)

                if use_rag:
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
                        if target_q is not None:
                            valid_chunks.sort(
                                key=lambda c: 0 if (getattr(c, "question_number", None) == target_q or f"question {target_q}" in c.text.lower()) else 1
                            )

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
                            f"{ACADEMIC_SOLVER_PROMPT}\n\n"
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
                    yield _sse({"type": "phase", "phase": "generating"})
                    system_prompt = (
                        "You are SS SPARK AI — an advanced, intelligent, conversational assistant.\n"
                        "- Answer naturally using your general knowledge and the full conversation history.\n"
                        "- Be accurate, thorough, and format code or math with appropriate markdown."
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

        # 4. Persist assistant message
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

        # 5. Final meta event
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
