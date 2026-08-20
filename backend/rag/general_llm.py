"""
rag/general_llm.py

Lightweight general-purpose LLM chat using the SAME API keys and provider
already configured in paperqa_connector.py (OpenAI / Gemini / Anthropic via litellm).

This is the fallback when:
  - No documents have been uploaded, OR
  - Documents exist but the question is NOT relevant to them.

Returns the same dict shape as paperqa_connector.query() so chat_service.py
can treat both paths uniformly, but with:
  - sources = []       (no document citations — honestly)
  - confidence = None  (not applicable)
  - status = "general" (sentinel for the frontend)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


def _get_candidate_models() -> list[str]:
    """Return a priority list of litellm model names based on available API keys."""
    models: list[str] = []
    if os.getenv("OPENAI_API_KEY", ""):
        models.extend(["gpt-4o-mini", "gpt-4o"])
    if os.getenv("NVIDIA_API_KEY", "") or os.getenv("NVIDIA_NIM_API_KEY", ""):
        n_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY", "")
        os.environ.setdefault("NVIDIA_API_KEY", n_key)
        os.environ.setdefault("NVIDIA_NIM_API_KEY", n_key)
        models.extend([
            "nvidia_nim/meta/llama-3.1-8b-instruct",
            "nvidia_nim/meta/llama-3.3-70b-instruct",
            "nvidia_nim/meta/llama-3.1-70b-instruct",
        ])
    if os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", ""):
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        os.environ.setdefault("GEMINI_API_KEY", key)
        os.environ.setdefault("GOOGLE_API_KEY", key)
        models.extend([
            "gemini/gemini-2.0-flash",
            "gemini/gemini-1.5-flash",
            "gemini/gemini-flash-lite-latest",
        ])
    if os.getenv("ANTHROPIC_API_KEY", ""):
        models.extend(["claude-3-5-haiku-20241022"])

    if models:
        return models

    raise RuntimeError(
        "No LLM API key found. Set OPENAI_API_KEY, GEMINI_API_KEY, NVIDIA_API_KEY, or "
        "ANTHROPIC_API_KEY in your backend/.env file."
    )


def _pick_llm() -> str:
    """Return primary model name."""
    return _get_candidate_models()[0]


async def general_chat(
    question: str,
    system_prompt: str | None = None,
    chat_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Send a question to the LLM with full multi-turn conversational history.

    Parameters
    ----------
    question:
        The user's message.
    system_prompt:
        Optional override. Defaults to a ChatGPT/Gemini/Claude-style assistant persona.
    chat_history:
        Optional list of prior messages in the format:
        [{"role": "user" | "assistant", "content": "..."}]

    Returns
    -------
    dict matching the shape returned by paperqa_connector.query():
        {
            "answer":     str,
            "sources":    [],
            "confidence": None,
            "references": "",
            "cost":       float,
            "status":     "general",
        }
    """
    try:
        import litellm  # already installed as a PaperQA dependency
    except ImportError as exc:
        raise RuntimeError(
            "litellm is not installed. It should be installed as a PaperQA dependency."
        ) from exc

    if system_prompt is None:
        system_prompt = (
            "You are SS SPARK AI — an advanced, intelligent, and helpful conversational AI "
            "assistant like ChatGPT, Claude, and Gemini.\n"
            "- Maintain continuous context across the conversation and follow-up questions.\n"
            "- Provide thorough, well-structured, and articulate answers.\n"
            "- Use clean Markdown formatting with headers, bullet points, and code blocks where appropriate.\n"
            "- Never fabricate false citations or document references.\n"
            "- If you are unsure about something, state so honestly."
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    # Append past conversation history (keeping last 16 messages for memory within context limits)
    if chat_history:
        for msg in chat_history[-16:]:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)})

    # Append current user question
    messages.append({"role": "user", "content": question})

    candidate_models = _get_candidate_models()
    last_error: Exception | None = None
    t0 = time.monotonic()

    for model in candidate_models:
        logger.info("general_chat: trying %s with %d messages in context", model, len(messages))
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                timeout=30.0,
            )
            answer = response.choices[0].message.content or ""
            cost = 0.0
            try:
                usage = response.usage
                if usage:
                    cost = round(
                        (getattr(usage, "prompt_tokens", 0) * 0.00000015)
                        + (getattr(usage, "completion_tokens", 0) * 0.0000006),
                        6,
                    )
            except Exception:
                pass

            elapsed = round(time.monotonic() - t0, 3)
            logger.info("general_chat: answered in %.3fs via %s (%d chars)", elapsed, model, len(answer))

            return {
                "answer": answer,
                "sources": [],
                "confidence": None,
                "references": "",
                "cost": cost,
                "status": "general",
            }
        except Exception as exc:
            logger.warning("general_chat attempt on %s failed: %s", model, exc)
            last_error = exc
            continue

    logger.error("general_chat all models failed: %s", last_error)
    return {
        "answer": (
            f"I encountered an error while answering: {last_error}\n\n"
            "Please verify your API key is valid and try again."
        ),
        "sources": [],
        "confidence": None,
        "references": "",
        "cost": 0.0,
        "status": "error",
    }


async def general_chat_stream(
    question: str,
    system_prompt: str | None = None,
    chat_history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields LLM token chunks as they arrive (streaming).

    Yields raw text chunks. The caller is responsible for SSE framing.
    Falls back to a single-chunk yield if streaming fails.
    """
    try:
        import litellm
    except ImportError as exc:
        yield f"Error: litellm not installed — {exc}"
        return

    if system_prompt is None:
        system_prompt = (
            "You are SS SPARK AI — an advanced, intelligent, and helpful conversational AI "
            "assistant like ChatGPT, Claude, and Gemini.\n"
            "- Maintain continuous context across the conversation and follow-up questions.\n"
            "- Provide thorough, well-structured, and articulate answers.\n"
            "- Use clean Markdown formatting with headers, bullet points, and code blocks where appropriate.\n"
            "- Never fabricate false citations or document references.\n"
            "- If you are unsure about something, state so honestly."
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if chat_history:
        for msg in chat_history[-16:]:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": question})

    candidate_models = _get_candidate_models()
    t0 = time.monotonic()

    for model in candidate_models:
        logger.info("general_chat_stream: trying %s (%d messages)", model, len(messages))
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                timeout=60.0,
                stream=True,
            )
            first_token = True
            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    if first_token:
                        elapsed = round(time.monotonic() - t0, 3)
                        logger.info(
                            "general_chat_stream: first token in %.3fs via %s", elapsed, model
                        )
                        first_token = False
                    yield delta.content
            return  # success — stop trying other models
        except Exception as exc:
            logger.warning("general_chat_stream %s failed: %s", model, exc)
            continue

    # All models failed — yield error text
    logger.error("general_chat_stream: all models failed")
    yield "I encountered an error while generating a response. Please verify your API key and try again."


# Set of fast-path conversational tokens that never require document RAG
_CONVERSATIONAL_GREETINGS = {
    "hi", "hello", "hey", "good morning", "good evening", "good afternoon",
    "how are you", "who are you", "what can you do", "help", "thanks",
    "thank you", "bye", "goodbye", "ping", "test"
}

_DOCUMENT_KEYWORD_SIGNALS = {
    "paper", "papers", "pdf", "exam", "syllabus", "pyq", "semester",
    "midterm", "cite", "citation", "page", "according to the document",
    "according to the paper", "according to the notes", "in the document",
    "in the paper", "in the notes", "in my document", "in my notes",
    "in my file", "in the file", "uploaded doc", "uploaded file",
    "uploaded notes", "from the document", "from the paper"
}


async def is_question_relevant_to_docs(
    question: str,
    doc_names: list[str],
    chat_history: list[dict[str, str]] | None = None,
) -> bool:
    """
    Decide whether the user's question requires document RAG or general conversational AI.
    Uses fast O(1) heuristic matching first, falling back to lightweight LLM classifier only when ambiguous.
    """
    if not doc_names:
        return False

    import re
    q_clean = re.sub(r"[^\w\s]", " ", question).strip().lower()
    q_clean_single = re.sub(r"\s+", " ", q_clean)

    # 1. Fast-path: Greetings and meta queries are never RAG
    if (
        q_clean_single in _CONVERSATIONAL_GREETINGS
        or any(q_clean_single.startswith(g + " ") or q_clean_single == g for g in ("hi", "hello", "hey", "good morning", "good evening", "how are you"))
    ):
        return False

    # 2. Fast-path: Document name or individual token / stem mention
    for n in doc_names:
        if n:
            base = n.lower().rsplit(".", 1)[0]
            if len(base) > 3 and base in q_clean:
                return True
            tokens = [t for t in re.split(r"[_\-\s]+", base) if len(t) > 2]
            if any(t in q_clean for t in tokens):
                return True
            # Root stem matching for morphological variants
            if any(len(t) >= 4 and t[:4] in q_clean for t in tokens):
                return True

    if any(sig in q_clean for sig in _DOCUMENT_KEYWORD_SIGNALS):
        return True

    # 3. If litellm is not importable, default to True
    try:
        import litellm
    except ImportError:
        return True

    candidate_models = _get_candidate_models()
    doc_list = "\n".join(f"- {name}" for name in doc_names[:10])

    recent_context = ""
    if chat_history:
        recent_turns = chat_history[-2:]
        formatted_turns = "\n".join(
            f"{m.get('role', 'user').capitalize()}: {str(m.get('content', ''))[:100]}"
            for m in recent_turns
            if m.get("content")
        )
        if formatted_turns:
            recent_context = f"Recent context:\n{formatted_turns}\n\n"

    classifier_prompt = (
        "Determine whether the user question is related to the topics of the uploaded documents, or is completely unrelated general chit-chat (e.g. greetings, recipes, trivia, geography, creative writing).\n"
        f"Uploaded Documents:\n{doc_list}\n\n"
        f"{recent_context}"
        f"Question: {question}\n\n"
        "If the question relates to the subjects or topics in the document titles, reply 'RAG'.\n"
        "If the question is completely unrelated general conversation/trivia/recipes/creative writing, reply 'GENERAL'.\n"
        "Reply with ONLY 'RAG' or 'GENERAL':"
    )

    for model in candidate_models:
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": classifier_prompt}],
                temperature=0.0,
                max_tokens=6,
                timeout=3.0,
            )
            verdict = (response.choices[0].message.content or "").strip().upper()
            logger.info("Relevance classifier verdict=%r (model=%s)", verdict, model)
            return verdict.startswith("RAG")
        except Exception as exc:
            logger.warning("Classifier failed on %s: %s", model, exc)
            continue

    # Default to RAG when docs exist if all classifier attempts fail
    return True


async def contextualize_query(
    question: str,
    chat_history: list[dict[str, str]] | None = None,
) -> str:
    """
    If there is prior conversation history and the question is an ambiguous follow-up,
    reformulate it into a self-contained search query. Otherwise returns question as-is.
    """
    if not chat_history:
        return question

    q_lower = question.strip().lower()
    words = q_lower.split()

    # Fast-path: Standalone questions with >= 6 words and no referential pronouns need no rewrite
    followup_signals = (
        " it", " its", " this", " that", " these", " those", " they", " them",
        "above", "previous", "earlier", "second", "third", "first",
        "more details", "expand", "explain more", "summarize that", "code for that",
        "translate", "why", "how", "what about", "what else", "tell me more"
    )
    is_likely_followup = len(words) < 5 or any(sig in f" {q_lower}" for sig in followup_signals)

    if not is_likely_followup:
        return question

    try:
        import litellm
    except ImportError:
        return question

    candidate_models = _get_candidate_models()
    recent_turns = chat_history[-4:]
    history_text = "\n".join(
        f"{m.get('role', 'user').capitalize()}: {str(m.get('content', ''))[:200]}"
        for m in recent_turns
        if m.get("content")
    )

    prompt = (
        "Rewrite the follow-up question into a concise standalone search query for document retrieval. "
        "Do NOT answer. If already standalone, return unchanged.\n\n"
        f"History:\n{history_text}\n\n"
        f"Follow-up: {question}\n\n"
        "Query:"
    )

    for model in candidate_models:
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=60,
                timeout=3.0,
            )
            rewritten = (response.choices[0].message.content or "").strip()
            if rewritten and len(rewritten) > 3:
                logger.info("Contextualized query from %r -> %r", question, rewritten)
                return rewritten
        except Exception as exc:
            logger.warning("Query contextualizer failed on %s: %s", model, exc)
            continue

    return question
