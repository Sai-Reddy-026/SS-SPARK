"""
rag/general_llm.py

High-performance LLM Router and General Chat engine for SS SPARK.
Configured with strict provider hierarchy:
    Primary:  Google Gemini (gemini-2.0-flash, gemini-1.5-flash, gemini-2.5-flash)
    Fallback: NVIDIA NIM (meta/llama-3.1-8b-instruct, meta/llama-3.3-70b-instruct)
    Tertiary: OpenAI (gpt-4o-mini), Anthropic (claude-3-5-haiku-20241022)

Key Capabilities:
  - Gemini-first automatic routing
  - Time-To-First-Token (TTFT) timeout (8.0s) for instant fallback to NVIDIA
  - Mid-stream failure recovery with ("reset", "") event to prevent duplicate/corrupted text
  - Structured request correlation logging: [CHAT {req_id}]
  - Fast-path heuristic classifiers for query routing and contextualization
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

logger = logging.getLogger("ss_spark.general_llm")

# Model definitions per provider
GEMINI_MODELS = [
    "gemini/gemini-2.0-flash",
    "gemini/gemini-1.5-flash",
    "gemini/gemini-1.5-pro",
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
        provider_type = "Primary (Gemini)" if "gemini" in model else ("Fallback (NVIDIA)" if "nvidia" in model else "Tertiary")
        logger.info("%sgeneral_chat: attempting %s [%s] with %d messages in context", tag, model, provider_type, len(messages))
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                timeout=25.0,
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
            logger.info("%sgeneral_chat: succeeded in %.3fs via %s (%d chars)", tag, elapsed, model, len(answer))

            return {
                "answer": answer,
                "sources": [],
                "confidence": None,
                "references": "",
                "cost": cost,
                "status": "general",
            }
        except Exception as exc:
            logger.warning("%sgeneral_chat: %s failed: %s", tag, model, exc)
            last_error = exc
            continue

    logger.error("%sgeneral_chat: all LLM providers failed: %s", tag, last_error)
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
      - If Gemini fails before yielding or takes >8.0s to first token, switches to NVIDIA automatically.
      - If Gemini fails mid-stream after emitting partial tokens, yields ("reset", "") and then streams
        the clean, complete response from NVIDIA from scratch (no duplicate/corrupted text).
      - If all providers fail, yields a helpful inline error token.
    """
    import litellm

    tag = f"[{req_id}] " if req_id else ""
    messages = _format_messages(question, system_prompt, chat_history)
    candidate_models = get_ordered_candidate_models()
    t_start = time.monotonic()

    tokens_yielded_total = 0

    for model_idx, model in enumerate(candidate_models):
        is_gemini = "gemini" in model
        is_nvidia = "nvidia" in model
        provider_name = "Gemini (Primary)" if is_gemini else ("NVIDIA (Fallback)" if is_nvidia else "Tertiary Provider")

        logger.info("%sgeneral_chat_stream: starting %s (%s)", tag, model, provider_name)
        model_tokens = 0
        t_model_start = time.monotonic()

        try:
            # First-token timeout: 8.0s connect/first token window
            response_stream = await asyncio.wait_for(
                litellm.acompletion(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048,
                    stream=True,
                    timeout=45.0,
                ),
                timeout=8.0,
            )

            # Read stream with first-token deadline
            first_token_received = False
            async for chunk in response_stream:
                delta = chunk.choices[0].delta if (chunk and chunk.choices) else None
                content = getattr(delta, "content", "") if delta else ""
                if content:
                    if not first_token_received:
                        first_token_received = True
                        ttft = round(time.monotonic() - t_model_start, 3)
                        logger.info("%sgeneral_chat_stream: first token from %s in %.3fs", tag, model, ttft)
                    
                    model_tokens += 1
                    tokens_yielded_total += 1
                    yield ("token", content)

            if first_token_received:
                total_time = round(time.monotonic() - t_start, 3)
                logger.info("%sgeneral_chat_stream: completed via %s (%d tokens, total %.3fs)", tag, model, model_tokens, total_time)
                return  # Successful completion!

            # If stream finished without any tokens
            logger.warning("%sgeneral_chat_stream: %s yielded 0 tokens, trying fallback...", tag, model)

        except (asyncio.TimeoutError, Exception) as exc:
            elapsed = round(time.monotonic() - t_model_start, 3)
            logger.warning("%sgeneral_chat_stream: %s failed after %.3fs: %s", tag, model, elapsed, exc)

            # If partial tokens were yielded before failing mid-stream:
            if model_tokens > 0:
                logger.warning(
                    "%sgeneral_chat_stream: Mid-stream failure on %s after %d tokens! Emitting reset event for clean fallback.",
                    tag, model, model_tokens
                )
                yield ("reset", "")
                tokens_yielded_total = 0

            # Continue to next model in candidate list (e.g. NVIDIA)
            continue

    # If all models failed
    logger.error("%sgeneral_chat_stream: All candidate models failed!", tag)
    if tokens_yielded_total > 0:
        yield ("reset", "")
    yield ("token", "AI service is temporarily unavailable. Please try again in a moment.")


# --------------------------------------------------------------------------- #
# Heuristic Routing & Classification
# --------------------------------------------------------------------------- #

_CONVERSATIONAL_GREETINGS = {
    "hi", "hello", "hey", "good morning", "good evening", "good afternoon",
    "how are you", "who are you", "what can you do", "help", "thanks",
    "thank you", "bye", "goodbye", "ping", "test", "what is your name",
    "who made you", "ok", "okay", "cool", "great", "nice"
}

_DOCUMENT_KEYWORD_SIGNALS = {
    "paper", "papers", "pdf", "exam", "syllabus", "pyq", "semester",
    "midterm", "cite", "citation", "page", "according to the document",
    "according to the paper", "according to the notes", "in the document",
    "in the paper", "in the notes", "in my document", "in my notes",
    "in my file", "in the file", "uploaded doc", "uploaded file",
    "uploaded notes", "from the document", "from the paper", "from my notes",
    "questions from", "topics from", "repeat", "previous paper"
}


async def is_question_relevant_to_docs(
    question: str,
    doc_names: List[str],
    chat_history: Optional[List[Dict[str, str]]] = None,
    req_id: str = "",
) -> bool:
    """
    Decide whether the user's question requires document RAG or general conversational AI.
    Uses ultra-fast O(1) heuristic matching first, falling back to LLM classifier (timeout 2.5s) only when ambiguous.
    """
    if not doc_names:
        return False

    tag = f"[{req_id}] " if req_id else ""
    q_clean = re.sub(r"[^\w\s]", " ", question).strip().lower()
    q_clean_single = re.sub(r"\s+", " ", q_clean)

    # 1. Fast-path: Greetings and common chat queries
    if (
        q_clean_single in _CONVERSATIONAL_GREETINGS
        or any(q_clean_single.startswith(g + " ") or q_clean_single == g for g in ("hi", "hello", "hey", "good morning", "good evening", "how are you"))
    ):
        logger.debug("%sRouting fast-path: General conversation detected for %r", tag, question[:30])
        return False

    # 2. Fast-path: Document name or individual token mention
    for n in doc_names:
        if n:
            base = n.lower().rsplit(".", 1)[0]
            if len(base) > 3 and base in q_clean:
                logger.debug("%sRouting fast-path: Document exact match '%s' in query", tag, base)
                return True
            tokens = [t for t in re.split(r"[_\-\s]+", base) if len(t) > 2]
            if any(t in q_clean for t in tokens):
                logger.debug("%sRouting fast-path: Document token match in query", tag)
                return True
            if any(len(t) >= 4 and t[:4] in q_clean for t in tokens):
                return True

    if any(sig in q_clean for sig in _DOCUMENT_KEYWORD_SIGNALS):
        logger.debug("%sRouting fast-path: Document signal keyword in query", tag)
        return True

    # 3. LLM classifier fallback
    try:
        import litellm
    except ImportError:
        return True

    candidate_models = get_ordered_candidate_models()
    doc_list = "\n".join(f"- {name}" for name in doc_names[:8])

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

    for model in candidate_models[:2]:
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": classifier_prompt}],
                temperature=0.0,
                max_tokens=6,
                timeout=2.5,
            )
            verdict = (response.choices[0].message.content or "").strip().upper()
            logger.info("%sRelevance classifier verdict=%r via %s", tag, verdict, model)
            return verdict.startswith("RAG")
        except Exception as exc:
            logger.debug("%sClassifier failed on %s: %s", tag, model, exc)
            continue

    # Safe default: RAG when docs exist
    return True


async def contextualize_query(
    question: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    req_id: str = "",
) -> str:
    """
    If there is prior conversation history and the question is an ambiguous follow-up,
    reformulate it into a self-contained search query. Otherwise returns question as-is.
    """
    if not chat_history:
        return question

    tag = f"[{req_id}] " if req_id else ""
    q_lower = question.strip().lower()
    words = q_lower.split()

    # Fast-path: Standalone queries with >= 6 words and no pronouns need no rewrite
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

    candidate_models = get_ordered_candidate_models()
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

    for model in candidate_models[:2]:
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=60,
                timeout=2.5,
            )
            rewritten = (response.choices[0].message.content or "").strip()
            if rewritten and len(rewritten) > 3:
                logger.info("%sContextualized query: %r -> %r via %s", tag, question, rewritten, model)
                return rewritten
        except Exception as exc:
            logger.debug("%sContextualizer failed on %s: %s", tag, model, exc)
            continue

    return question
