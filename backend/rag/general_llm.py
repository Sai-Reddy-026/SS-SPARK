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

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _get_candidate_models() -> list[str]:
    """Return a priority list of litellm model names based on available API keys."""
    if os.getenv("OPENAI_API_KEY", ""):
        return ["gpt-4o-mini", "gpt-4o"]
    if os.getenv("GEMINI_API_KEY", ""):
        key = os.getenv("GEMINI_API_KEY", "")
        os.environ.setdefault("GOOGLE_API_KEY", key)
        return ["gemini/gemini-flash-latest", "gemini/gemini-3.7-flash", "gemini/gemini-pro-latest"]
    if os.getenv("ANTHROPIC_API_KEY", ""):
        return ["claude-3-5-haiku-20241022"]
    raise RuntimeError(
        "No LLM API key found. Set OPENAI_API_KEY, GEMINI_API_KEY, or "
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

    for model in candidate_models:
        logger.info("general_chat: trying %s with %d messages in context", model, len(messages))
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
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


async def is_question_relevant_to_docs(
    question: str,
    doc_names: list[str],
    chat_history: list[dict[str, str]] | None = None,
) -> bool:
    """
    Ask the LLM whether the user's question is likely answerable using
    the listed uploaded document names, taking recent conversation into account.

    Returns True  → route to RAG
    Returns False → route to general_chat
    """
    if not doc_names:
        return False

    try:
        import litellm
    except ImportError:
        # If litellm is missing, conservatively use RAG when docs exist
        return True

    candidate_models = _get_candidate_models()
    doc_list = "\n".join(f"- {name}" for name in doc_names[:20])

    recent_context = ""
    if chat_history:
        recent_turns = chat_history[-4:]
        formatted_turns = "\n".join(
            f"{m.get('role', 'user').capitalize()}: {str(m.get('content', ''))[:150]}"
            for m in recent_turns
            if m.get("content")
        )
        if formatted_turns:
            recent_context = f"Recent conversation context:\n{formatted_turns}\n\n"

    classifier_prompt = (
        "You are a routing classifier. Given a user question, recent conversation context, "
        "and a list of uploaded document names, decide whether the question is specifically asking "
        "about the content of those documents, OR whether it is a general knowledge question "
        "that does not require those documents.\n\n"
        f"Uploaded documents:\n{doc_list}\n\n"
        f"{recent_context}"
        f"User question: {question}\n\n"
        "Reply with ONLY one word:\n"
        "  RAG      — the question is specifically about the uploaded documents or references document content\n"
        "  GENERAL  — the question is general knowledge, coding help, greetings, or unrelated to the documents\n\n"
        "Your answer:"
    )

    for model in candidate_models:
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": classifier_prompt}],
                temperature=0.0,
                max_tokens=10,
            )
            verdict = (response.choices[0].message.content or "").strip().upper()
            logger.info(
                "Relevance classifier verdict=%r (model=%s) for question=%r",
                verdict,
                model,
                question[:80],
            )
            return verdict.startswith("RAG")
        except Exception as exc:
            logger.warning("Classifier failed on %s: %s", model, exc)
            continue

    # Default to RAG if all classifier attempts fail
    return True


async def contextualize_query(
    question: str,
    chat_history: list[dict[str, str]] | None = None,
) -> str:
    """
    If there is prior conversation history and the question appears to be a follow-up
    (e.g., uses pronouns or referential phrases like 'it', 'that', 'this', 'explain more', 'second point'),
    reformulate it into a self-contained search query for RAG document retrieval.

    If the question is already standalone or no history exists, returns the question as-is.
    """
    if not chat_history:
        return question

    q_lower = question.strip().lower()
    # Check if question contains follow-up indicators or is short
    followup_signals = [
        " it", " this", " that", " these", " those", " they", " them",
        "above", "previous", "earlier", "second", "third", "first",
        "more details", "expand", "explain more", "summarize that", "code for that",
        "translate", "why", "how", "what about", "what else", "tell me more"
    ]
    is_likely_followup = len(q_lower.split()) < 12 or any(sig in f" {q_lower}" for sig in followup_signals)

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
        "Given the conversation history and a follow-up question, rewrite the follow-up "
        "question into a standalone, concise search query containing all necessary keywords "
        "to search within relevant documents. Do NOT answer the question. "
        "If it is already standalone, return it unchanged.\n\n"
        f"Conversation history:\n{history_text}\n\n"
        f"Follow-up question: {question}\n\n"
        "Standalone search query (one line only):"
    )

    for model in candidate_models:
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=60,
            )
            rewritten = (response.choices[0].message.content or "").strip()
            if rewritten and len(rewritten) > 3:
                logger.info("Contextualized query from %r -> %r", question, rewritten)
                return rewritten
        except Exception as exc:
            logger.warning("Query contextualizer failed on %s: %s", model, exc)
            continue

    return question
