"""
rag/general_llm.py

High-performance LLM Router and General Chat engine for SS SPARK.
Configured with strict provider hierarchy:
    Primary:  Google Gemini (gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-pro)
    Fallback: NVIDIA NIM (meta/llama-3.1-8b-instruct, meta/llama-3.3-70b-instruct, meta/llama-3.1-70b-instruct)
    Tertiary: OpenAI (gpt-4o-mini), Anthropic (claude-3-5-haiku-20241022)

Key Capabilities:
  - Gemini-first automatic routing
  - Hard First-Token Timeout (3.5s) on __anext__() for instant fallback to NVIDIA
  - Mid-stream failure recovery with ("reset", "") event to prevent duplicate/corrupted text
  - Fast, deterministic, pure-Python local routing heuristic (<1ms, 0 LLM calls)
  - Fast, deterministic local query contextualization (<1ms, 0 LLM calls)
  - Structured request correlation logging: [CHAT {req_id}] with pin-to-pin milestone tracking
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

logger = logging.getLogger("ss_spark.general_llm")

# Hard First-Token Timeout in seconds
FIRST_TOKEN_TIMEOUT_S = 3.5

# Model definitions per provider
GEMINI_MODELS = [
    "gemini/gemini-2.0-flash",
    "gemini/gemini-2.0-flash-lite",
    "gemini/gemini-1.5-flash",
]

NVIDIA_MODELS = [
    "nvidia_nim/meta/llama-3.1-8b-instruct",
    "nvidia_nim/meta/llama-3.3-70b-instruct",
    "nvidia_nim/meta/llama-3.1-70b-instruct",
]

OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
]

ANTHROPIC_MODELS = [
    "claude-3-5-haiku-20241022",
]


def _ensure_env_synced() -> None:
    """Ensure core settings are loaded and all environment variable aliases are populated."""
    try:
        from core.config import get_settings
        cfg = get_settings()
        cfg.apply_to_env()
    except Exception as exc:
        logger.debug("Failed to sync settings: %s", exc)


def get_model_tiers() -> Dict[str, List[str]]:
    """
    Return available models grouped by tier:
      - 'primary': Gemini models if GEMINI_API_KEY/GOOGLE_API_KEY is available
      - 'fallback': NVIDIA models if NVIDIA_API_KEY/NVIDIA_NIM_API_KEY is available
      - 'tertiary': OpenAI / Anthropic models if available
    """
    _ensure_env_synced()
    tiers: Dict[str, List[str]] = {
        "primary": [],
        "fallback": [],
        "tertiary": [],
    }

    gemini_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    nvidia_key = (os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY") or "").strip()
    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    anthropic_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()

    # 1. Primary: Gemini
    if gemini_key:
        tiers["primary"].extend(GEMINI_MODELS)

    # 2. Fallback: NVIDIA NIM
    if nvidia_key:
        tiers["fallback"].extend(NVIDIA_MODELS)

    # 3. Tertiary: OpenAI / Anthropic
    if openai_key:
        tiers["tertiary"].extend(OPENAI_MODELS)
    if anthropic_key:
        tiers["tertiary"].extend(ANTHROPIC_MODELS)

    # If Gemini is missing but NVIDIA is available, promote NVIDIA to primary
    if not tiers["primary"]:
        if tiers["fallback"]:
            tiers["primary"] = tiers["fallback"]
            tiers["fallback"] = tiers["tertiary"]
            tiers["tertiary"] = []
        elif tiers["tertiary"]:
            tiers["primary"] = tiers["tertiary"]
            tiers["tertiary"] = []

    return tiers


def get_ordered_candidate_models() -> List[str]:
    """Return flattened list of candidate models in strict execution priority order."""
    tiers = get_model_tiers()
    models = []
    for tier_name in ("primary", "fallback", "tertiary"):
        for m in tiers[tier_name]:
            if m not in models:
                models.append(m)

    if not models:
        raise RuntimeError(
            "No LLM API key configured. Please set GEMINI_API_KEY or NVIDIA_API_KEY in backend/.env"
        )
    return models


def _format_messages(
    question: str,
    system_prompt: Optional[str] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """Build sanitized chat messages list for LiteLLM with system prompt and history."""
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

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if chat_history:
        for msg in chat_history[-16:]:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)})

    messages.append({"role": "user", "content": question})
    return messages


async def general_chat(
    question: str,
    system_prompt: Optional[str] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
    req_id: str = "",
) -> Dict[str, Any]:
    """
    Non-streaming LLM invocation with Gemini primary -> NVIDIA fallback.

    Returns dict matching standard shape:
      {
          "answer": str,
          "sources": [],
          "confidence": None,
          "references": "",
          "cost": float,
          "status": "general" | "success" | "error",
      }
    """
    import litellm

    tag = f"[{req_id}] " if req_id else ""
    messages = _format_messages(question, system_prompt, chat_history)
    candidate_models = get_ordered_candidate_models()
    last_error: Optional[Exception] = None
    t0 = time.monotonic()

    for model in candidate_models:
        is_gemini = "gemini" in model
        is_nvidia = "nvidia" in model
        provider_name = "gemini" if is_gemini else ("nvidia" if is_nvidia else "tertiary")
        logger.info("%sllm_start provider=%s model=%s (%d messages)", tag, provider_name, model, len(messages))

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                timeout=15.0,
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
            logger.info("%sllm_complete in %.3fs via %s (%d chars)", tag, elapsed, model, len(answer))

            return {
                "answer": answer,
                "sources": [],
                "confidence": None,
                "references": "",
                "cost": cost,
                "status": "general",
            }
        except Exception as exc:
            logger.warning("%smodel %s failed (non-fatal): %s", tag, model, exc)
            last_error = exc
            continue

    logger.error("%sall LLM providers failed: %s", tag, last_error)
    return {
        "answer": "AI service is temporarily unavailable. Please try again in a moment.",
        "sources": [],
        "confidence": None,
        "references": "",
        "cost": 0.0,
        "status": "error",
    }


async def general_chat_stream(
    question: str,
    system_prompt: Optional[str] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
    req_id: str = "",
) -> AsyncGenerator[Tuple[str, str], None]:
    """
    Streaming LLM invocation yielding tuples (event_type, payload):
        ("token", token_text)  — standard LLM token
        ("reset", "")          — emitted if a mid-stream provider switch occurs

    Guarantees:
      - Gemini is attempted first.
      - First-token timeout (3.5s) is wrapped directly on __anext__() so stalled
        Gemini streams fail over to NVIDIA immediately without hanging for 45s.
      - If Gemini fails mid-stream after emitting partial tokens, yields ("reset", "") and then streams
        the clean, complete response from NVIDIA from scratch (0 duplicate text).
      - If all providers fail, yields a helpful inline error token.
    """
    import litellm

    tag = f"[{req_id}] " if req_id else ""
    messages = _format_messages(question, system_prompt, chat_history)
    candidate_models = get_ordered_candidate_models()
    t_start = time.monotonic()

    tokens_yielded_total = 0
    primary_attempted = False

    for model_idx, model in enumerate(candidate_models):
        is_gemini = "gemini" in model
        is_nvidia = "nvidia" in model
        provider_name = "gemini" if is_gemini else ("nvidia" if is_nvidia else "tertiary")

        if is_gemini:
            logger.info("%sllm_start provider=gemini model=%s", tag, model)
            primary_attempted = True
        elif is_nvidia and primary_attempted:
            logger.info("%sfallback provider=nvidia model=%s", tag, model)
        else:
            logger.info("%sllm_start provider=%s model=%s", tag, provider_name, model)

        model_tokens = 0
        t_model_start = time.monotonic()
        response_stream = None

        try:
            # 1. Initiate async stream connection
            response_stream = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                stream=True,
                timeout=30.0,
            )

            # 2. Hard First-Token Timeout (3.5s) directly on __anext__()
            first_chunk = await asyncio.wait_for(
                response_stream.__anext__(),
                timeout=FIRST_TOKEN_TIMEOUT_S,
            )

            # Process first chunk
            first_delta = first_chunk.choices[0].delta if (first_chunk and first_chunk.choices) else None
            first_content = getattr(first_delta, "content", "") if first_delta else ""

            ttft_ms = round((time.monotonic() - t_model_start) * 1000, 2)
            logger.info("%sfirst_token provider=%s in %.2fms", tag, provider_name, ttft_ms)

            if first_content:
                model_tokens += 1
                tokens_yielded_total += 1
                yield ("token", first_content)

            # 3. Stream remaining chunks
            async for chunk in response_stream:
                delta = chunk.choices[0].delta if (chunk and chunk.choices) else None
                content = getattr(delta, "content", "") if delta else ""
                if content:
                    model_tokens += 1
                    tokens_yielded_total += 1
                    yield ("token", content)

            # Completed stream successfully
            total_time_ms = round((time.monotonic() - t_start) * 1000, 2)
            logger.info("%sstream_complete provider=%s in %.2fms | total_tokens=%d", tag, provider_name, total_time_ms, model_tokens)
            return

        except (asyncio.TimeoutError, StopAsyncIteration, Exception) as exc:
            elapsed_ms = round((time.monotonic() - t_model_start) * 1000, 2)
            logger.warning("%sprovider %s (%s) failed after %.2fms: %s", tag, provider_name, model, elapsed_ms, exc)

            # Cleanly close lingering stream
            if response_stream is not None:
                try:
                    if hasattr(response_stream, "aclose"):
                        await response_stream.aclose()
                    elif hasattr(response_stream, "close"):
                        response_stream.close()
                except Exception:
                    pass

            # If partial tokens were already yielded before failure mid-stream:
            if model_tokens > 0:
                logger.warning(
                    "%smid-stream failure on %s after %d tokens — emitting reset event for clean fallback",
                    tag, model, model_tokens
                )
                yield ("reset", "")
                tokens_yielded_total = 0

            # Continue to fallback model (e.g. NVIDIA)
            continue

    # If all models failed
    logger.error("%sall candidate LLM providers failed!", tag)
    if tokens_yielded_total > 0:
        yield ("reset", "")
    yield ("token", "AI service is temporarily unavailable. Please try again in a moment.")


# --------------------------------------------------------------------------- #
# Fast Local Deterministic Heuristics (<1ms, 0 LLM calls)
# --------------------------------------------------------------------------- #

_PURE_CHITCHAT_PATTERNS = {
    "hi", "hello", "hey", "good morning", "good evening", "good afternoon",
    "how are you", "who are you", "what can you do", "help", "thanks",
    "thank you", "bye", "goodbye", "ping", "test", "what is your name",
    "who made you", "ok", "okay", "cool", "great", "nice", "yo", "sup"
}

_EXPLICIT_DOCUMENT_PATTERNS = (
    "this document", "this pdf", "according to the notes", "in the uploaded file",
    "from the document", "from the paper", "from my notes", "in my notes",
    "what does page", "according to the image", "in the question paper",
    "exam", "syllabus", "pyq", "midterm", "semester", "page ", "chapter",
    "unit ", "diagram", "table", "formula", "question 1", "question 2",
    "question 3", "question 4", "question 5", "q1", "q2", "q3", "q4", "q5",
    "questions from", "topics from", "repeat", "previous paper", "marks",
    "uploaded doc", "uploaded file", "uploaded notes", "in my file", "in the file"
)


def is_question_relevant_to_docs(
    question: str,
    doc_names: List[str],
    chat_history: Optional[List[Dict[str, str]]] = None,
    req_id: str = "",
) -> bool:
    """
    Fast, deterministic local Python heuristic to decide whether to query documents via RAG.
    Zero LLM calls. Executes in <0.1 milliseconds.

    Logic:
      1. If user has 0 uploaded documents -> False (pure conversational AI).
      2. If question is an obvious standalone greeting -> False.
      3. If question mentions explicit document keywords -> True.
      4. If question matches any uploaded document filename/tokens -> True.
      5. If documents exist and there is uncertainty -> PREFER True (RAG retrieval).
    """
    if not doc_names:
        return False

    q_clean = re.sub(r"[^\w\s]", " ", question).strip().lower()
    q_single = re.sub(r"\s+", " ", q_clean)

    # 1. Pure greeting check (e.g. "hi", "hello", "how are you")
    if (
        q_single in _PURE_CHITCHAT_PATTERNS
        or any(q_single.startswith(g + " ") for g in ("hi", "hello", "hey", "good morning", "good evening", "good afternoon"))
    ):
        # Unless user explicitly references document in greeting
        if not any(pat in q_single for pat in ("doc", "pdf", "notes", "paper")):
            return False

    # 2. Explicit document signals
    if any(pat in q_single for pat in _EXPLICIT_DOCUMENT_PATTERNS):
        return True

    # 3. Document name & token matching
    for n in doc_names:
        if n:
            base = n.lower().rsplit(".", 1)[0]
            if len(base) >= 3 and base in q_single:
                return True
            tokens = [t for t in re.split(r"[_\-\s]+", base) if len(t) >= 3]
            if any(t in q_single for t in tokens):
                return True

    # 4. Safe default when documents exist: Search user documents
    return True


def contextualize_query(
    question: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    req_id: str = "",
) -> str:
    """
    Fast, deterministic local Python query contextualization for follow-up questions.
    Zero LLM calls. Executes in <0.1 milliseconds.

    Logic:
      - If no chat history or query is standalone -> return question as-is.
      - If query has follow-up signals ('its', 'this', 'that', 'advantages', etc.) and a previous
        topic is identifiable -> merge topic with query.
    """
    if not chat_history:
        return question

    q_lower = question.strip().lower()
    words = q_lower.split()

    followup_signals = (
        " it", " its", " this", " that", " these", " those", " they", " them",
        "above", "previous", "earlier", "second", "third", "first",
        "more details", "expand", "explain more", "summarize that", "code for that",
        "why", "how", "what about", "what else", "tell me more",
        "advantages", "disadvantages", "features", "examples"
    )

    is_followup = len(words) < 5 or any(sig in f" {q_lower}" for sig in followup_signals)
    if not is_followup:
        return question

    # Find the most recent user turn in history
    last_user_query = ""
    for msg in reversed(chat_history):
        if msg.get("role") == "user" and msg.get("content"):
            last_user_query = str(msg.get("content", "")).strip()
            break

    if not last_user_query:
        return question

    # Extract meaningful key terms from the previous user turn (excluding stopwords)
    stopwords = {
        "what", "when", "where", "which", "whose", "why", "how", "is", "are", "was",
        "were", "the", "a", "an", "in", "on", "of", "to", "for", "with", "explain",
        "describe", "tell", "me", "about", "can", "you", "please", "give"
    }
    prev_words = [w for w in re.findall(r"\w+", last_user_query.lower()) if len(w) >= 3 and w not in stopwords]

    if prev_words:
        topic_phrase = " ".join(prev_words[:4])
        # If question already contains the topic words, return as-is
        if all(w in q_lower for w in prev_words[:2]):
            return question
        merged = f"{topic_phrase} {question}"
        return merged

    return question
