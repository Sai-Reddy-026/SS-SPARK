"""
backend/tests/test_ai_chat_audit.py

Comprehensive test suite verifying the AI chat latency and reliability fixes:
  TEST 1:  General question does NOT make classifier LLM call.
  TEST 2:  Document question does NOT make classifier LLM call.
  TEST 3:  Document question does NOT make contextualizer LLM call.
  TEST 4:  Gemini first token arrives quickly -> Gemini continues.
  TEST 5:  Gemini first token takes >3.5 seconds -> NVIDIA fallback occurs.
  TEST 6:  Gemini fails before first token -> NVIDIA fallback.
  TEST 7:  Gemini fails after partial tokens -> reset event + clean NVIDIA response.
  TEST 8:  No duplicate done events emitted.
  TEST 9:  No infinite loading / stream always completes.
  TEST 10: Multiple concurrent users remain isolated.
  TEST 11: RAG question still retrieves correct document chunks & citations.
  TEST 12: General question bypasses RAG and streams directly.
  TEST 13: Production SSE headers and security diagnostics.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from core.config import get_settings
from rag import general_llm
from services.chat_service import ask_question_stream, ask_question

client = TestClient(app)


def parse_sse_events(raw_text: str) -> list[dict]:
    """Parse raw SSE text chunks into event dicts."""
    events = []
    for line in raw_text.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str:
                try:
                    events.append(json.loads(data_str))
                except json.JSONDecodeError:
                    pass
    return events


class AsyncIteratorMock:
    """Helper mock for async stream chunks."""
    def __init__(self, items, delay_first: float = 0.0):
        self.items = items
        self.index = 0
        self.delay_first = delay_first

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index == 0 and self.delay_first > 0:
            await asyncio.sleep(self.delay_first)
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        if isinstance(item, Exception):
            raise item
        return item


def _create_mock_chunk(text: str):
    mock_delta = MagicMock()
    mock_delta.content = text
    mock_choice = MagicMock()
    mock_choice.delta = mock_delta
    mock_chunk = MagicMock()
    mock_chunk.choices = [mock_choice]
    return mock_chunk


class TestAIChatAudit(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = "mock-gemini-key"
        os.environ["GOOGLE_API_KEY"] = "mock-gemini-key"
        os.environ["NVIDIA_API_KEY"] = "mock-nvidia-key"
        os.environ["NVIDIA_NIM_API_KEY"] = "mock-nvidia-key"
        self.cfg = get_settings()
        self.cfg.apply_to_env()

    # ---------------------------------------------------------------------- #
    # TEST 1: General question does NOT make classifier LLM call
    # ---------------------------------------------------------------------- #
    async def test_01_general_question_no_classifier_llm(self):
        """Verify that general questions trigger zero pre-flight LLM calls."""
        mock_chunks = [_create_mock_chunk("Hello! How can I help you today?")]

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = AsyncIteratorMock(mock_chunks)

            events = []
            async for chunk in ask_question_stream("Hello, how are you?", session_id="test-no-classifier"):
                events.extend(parse_sse_events(chunk))

            # Only 1 acompletion call should have been made (the streaming generation call itself)
            self.assertEqual(mock_llm.call_count, 1)
            call_kwargs = mock_llm.call_args_list[0][1]
            self.assertTrue(call_kwargs.get("stream", False), "Single LLM call must be the streaming generation call")

    # ---------------------------------------------------------------------- #
    # TEST 2 & 3: Document question does NOT make classifier or contextualizer LLM call
    # ---------------------------------------------------------------------- #
    async def test_02_03_document_question_no_classifier_or_contextualizer_llm(self):
        """Verify that questions with uploaded documents trigger zero pre-flight LLM calls."""
        from rag.retriever import RetrievedChunk, RetrievalResult

        mock_chunks = [
            RetrievedChunk(
                id="c1",
                doc_id="d1",
                source="os_notes.pdf",
                page=5,
                text="Process synchronization uses semaphores and mutex locks.",
                relevance=0.85,
            )
        ]
        llm_stream = [_create_mock_chunk("Semaphores are used for process synchronization.")]

        with patch("services.chat_service._get_cached_documents", new_callable=AsyncMock) as mock_docs, \
             patch("rag.retriever.retrieve", new_callable=AsyncMock) as mock_ret, \
             patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:

            mock_doc_obj = MagicMock()
            mock_doc_obj.name = "os_notes.pdf"
            mock_docs.return_value = [mock_doc_obj]
            mock_ret.return_value = RetrievalResult(mock_chunks)
            mock_llm.return_value = AsyncIteratorMock(llm_stream)

            history = [{"role": "user", "content": "What is process synchronization in os_notes.pdf?"}]
            events = []
            async for chunk in ask_question_stream(
                "What about its advantages?",
                session_id="test-doc-no-llm-routing",
            ):
                events.extend(parse_sse_events(chunk))

            # Exactly 1 LLM call must have occurred (for streaming the answer). No classifier or contextualizer calls!
            self.assertEqual(mock_llm.call_count, 1)
            call_kwargs = mock_llm.call_args_list[0][1]
            self.assertTrue(call_kwargs.get("stream", False))

    # ---------------------------------------------------------------------- #
    # TEST 4: Gemini first token arrives quickly -> Gemini continues
    # ---------------------------------------------------------------------- #
    async def test_04_gemini_fast_first_token_continues(self):
        """Verify Gemini completes normally when its first token arrives in time."""
        mock_chunks = [
            _create_mock_chunk("Gemini "),
            _create_mock_chunk("fast "),
            _create_mock_chunk("response."),
        ]

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = AsyncIteratorMock(mock_chunks, delay_first=0.05)

            tokens = []
            async for chunk in ask_question_stream("What is TCP?", session_id="test-gemini-fast"):
                for ev in parse_sse_events(chunk):
                    if ev.get("type") == "token":
                        tokens.append(ev.get("content", ""))

            self.assertEqual("".join(tokens), "Gemini fast response.")
            first_model = mock_llm.call_args_list[0][1]["model"]
            self.assertTrue("gemini" in first_model)

    # ---------------------------------------------------------------------- #
    # TEST 5: Gemini first token takes >3.5s -> NVIDIA fallback occurs
    # ---------------------------------------------------------------------- #
    async def test_05_gemini_first_token_timeout_nvidia_fallback(self):
        """Verify when Gemini takes >3.5s on __anext__(), it times out and switches to NVIDIA immediately."""
        nvidia_chunks = [
            _create_mock_chunk("NVIDIA "),
            _create_mock_chunk("fallback "),
            _create_mock_chunk("answer."),
        ]

        async def mock_acompletion_side_effect(*args, **kwargs):
            model = kwargs.get("model", "")
            if "gemini" in model:
                # Gemini takes 5.0s to deliver the first token (exceeding 3.5s timeout)
                return AsyncIteratorMock([_create_mock_chunk("Too late")], delay_first=4.0)
            elif "nvidia" in model:
                return AsyncIteratorMock(nvidia_chunks, delay_first=0.01)
            raise Exception(f"Unexpected model: {model}")

        with patch("litellm.acompletion", side_effect=mock_acompletion_side_effect) as mock_llm:
            tokens = []
            resets = 0
            async for chunk in ask_question_stream("Explain DNS", session_id="test-gemini-ttft-timeout"):
                for ev in parse_sse_events(chunk):
                    if ev.get("type") == "token":
                        tokens.append(ev.get("content", ""))
                    elif ev.get("type") == "reset":
                        resets += 1

            full_text = "".join(tokens)
            self.assertEqual(full_text, "NVIDIA fallback answer.")
            models_attempted = [call[1]["model"] for call in mock_llm.call_args_list]
            self.assertTrue(any("gemini" in m for m in models_attempted))
            self.assertTrue(any("nvidia" in m for m in models_attempted))

    # ---------------------------------------------------------------------- #
    # TEST 6: Gemini fails before first token -> NVIDIA fallback
    # ---------------------------------------------------------------------- #
    async def test_06_gemini_fails_before_first_token_nvidia_fallback(self):
        """Verify when Gemini immediately raises an error, NVIDIA responds without error."""
        nvidia_chunks = [_create_mock_chunk("NVIDIA response after Gemini immediate error.")]

        async def mock_acompletion_side_effect(*args, **kwargs):
            model = kwargs.get("model", "")
            if "gemini" in model:
                raise Exception("429 Too Many Requests: Rate limit exceeded")
            elif "nvidia" in model:
                return AsyncIteratorMock(nvidia_chunks)
            raise Exception(f"Unexpected model: {model}")

        with patch("litellm.acompletion", side_effect=mock_acompletion_side_effect):
            tokens = []
            async for chunk in ask_question_stream("Explain HTTP", session_id="test-gemini-fail-early"):
                for ev in parse_sse_events(chunk):
                    if ev.get("type") == "token":
                        tokens.append(ev.get("content", ""))

            self.assertEqual("".join(tokens), "NVIDIA response after Gemini immediate error.")

    # ---------------------------------------------------------------------- #
    # TEST 7: Gemini fails after partial tokens -> reset + NVIDIA
    # ---------------------------------------------------------------------- #
    async def test_07_gemini_midstream_failure_reset_and_fallback(self):
        """Verify mid-stream crash emits a reset event and NVIDIA yields clean text."""
        gemini_crash = [
            _create_mock_chunk("Partial "),
            _create_mock_chunk("broken "),
            Exception("Socket closed mid-stream"),
        ]
        nvidia_clean = [
            _create_mock_chunk("Clean "),
            _create_mock_chunk("NVIDIA "),
            _create_mock_chunk("response."),
        ]

        async def mock_acompletion_side_effect(*args, **kwargs):
            model = kwargs.get("model", "")
            if "gemini" in model:
                return AsyncIteratorMock(gemini_crash)
            elif "nvidia" in model:
                return AsyncIteratorMock(nvidia_clean)
            raise Exception(f"Unexpected model: {model}")

        with patch("litellm.acompletion", side_effect=mock_acompletion_side_effect):
            tokens = []
            resets = 0
            async for chunk in ask_question_stream("Explain Sorting", session_id="test-midstream-reset"):
                for ev in parse_sse_events(chunk):
                    if ev.get("type") == "reset":
                        resets += 1
                        tokens.clear()  # Clear on reset
                    elif ev.get("type") == "token":
                        tokens.append(ev.get("content", ""))

            self.assertGreaterEqual(resets, 1)
            self.assertEqual("".join(tokens), "Clean NVIDIA response.")

    # ---------------------------------------------------------------------- #
    # TEST 8 & 9: No duplicate done events & No infinite loading
    # ---------------------------------------------------------------------- #
    async def test_08_09_no_duplicate_done_and_no_infinite_loading(self):
        """Verify stream always terminates with exactly one done event."""
        mock_chunks = [_create_mock_chunk("Sample answer")]

        with patch("litellm.acompletion", return_value=AsyncIteratorMock(mock_chunks)):
            events = []
            async for chunk in ask_question_stream("Hello", session_id="test-done-count"):
                events.extend(parse_sse_events(chunk))

            done_events = [e for e in events if e.get("type") == "done"]
            self.assertEqual(len(done_events), 1, "Must emit exactly ONE 'done' event")

    # ---------------------------------------------------------------------- #
    # TEST 10: Multiple concurrent users remain isolated
    # ---------------------------------------------------------------------- #
    async def test_10_concurrent_user_isolation(self):
        """Verify concurrent requests execute independently without cross-contamination."""
        async def run_single_chat(session_id: str, prompt: str):
            chunks = [_create_mock_chunk(f"Answer for {prompt}")]
            with patch("litellm.acompletion", return_value=AsyncIteratorMock(chunks)):
                tokens = []
                async for chunk in ask_question_stream(prompt, session_id=session_id):
                    for ev in parse_sse_events(chunk):
                        if ev.get("type") == "token":
                            tokens.append(ev.get("content", ""))
                return session_id, "".join(tokens)

        tasks = [
            run_single_chat(f"sess-{i}", f"Question {i}")
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)
        for sid, text in results:
            idx = sid.split("-")[1]
            self.assertEqual(text, f"Answer for Question {idx}")

    # ---------------------------------------------------------------------- #
    # TEST 11: RAG question still retrieves correct chunks
    # ---------------------------------------------------------------------- #
    async def test_11_rag_retrieves_correct_chunks(self):
        """Verify vector retrieval accurately attaches document citations."""
        from rag.retriever import RetrievedChunk, RetrievalResult

        mock_chunks = [
            RetrievedChunk(
                id="c101",
                doc_id="d101",
                source="CN_Unit3.pdf",
                page=22,
                text="BGP uses path vector routing algorithm across autonomous systems.",
                relevance=0.92,
            )
        ]
        llm_answer = [_create_mock_chunk("BGP uses path vector routing as stated in CN_Unit3.pdf.")]

        with patch("services.chat_service._get_cached_documents", new_callable=AsyncMock) as mock_docs, \
             patch("rag.retriever.retrieve", new_callable=AsyncMock) as mock_ret, \
             patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:

            mock_doc_obj = MagicMock()
            mock_doc_obj.name = "CN_Unit3.pdf"
            mock_docs.return_value = [mock_doc_obj]
            mock_ret.return_value = RetrievalResult(mock_chunks)
            mock_llm.return_value = AsyncIteratorMock(llm_answer)

            events = []
            async for chunk in ask_question_stream("What does CN_Unit3.pdf say about BGP?", session_id="test-rag-chunks"):
                events.extend(parse_sse_events(chunk))

            meta_events = [e for e in events if e.get("type") == "meta"]
            self.assertEqual(len(meta_events), 1)
            meta = meta_events[0]
            self.assertEqual(meta.get("source"), "CN_Unit3.pdf")
            self.assertEqual(meta.get("page"), 22)
            self.assertEqual(meta["citations"][0]["source"], "CN_Unit3.pdf")

    # ---------------------------------------------------------------------- #
    # TEST 12: General question bypasses RAG
    # ---------------------------------------------------------------------- #
    async def test_12_general_question_bypasses_rag(self):
        """Verify general greeting completely bypasses retriever."""
        mock_chunks = [_create_mock_chunk("Hi there!")]

        with patch("rag.retriever.retrieve", new_callable=AsyncMock) as mock_ret, \
             patch("litellm.acompletion", return_value=AsyncIteratorMock(mock_chunks)):

            events = []
            async for chunk in ask_question_stream("hi", session_id="test-bypass-rag"):
                events.extend(parse_sse_events(chunk))

            # Vector retrieve must NOT have been called for a simple greeting
            self.assertEqual(mock_ret.call_count, 0)
            meta_events = [e for e in events if e.get("type") == "meta"]
            self.assertEqual(meta_events[0].get("status"), "general")

    # ---------------------------------------------------------------------- #
    # TEST 13: Production SSE Headers & Diagnostics
    # ---------------------------------------------------------------------- #
    def test_13_production_headers_and_diagnostics(self):
        """Verify FastAPI endpoint headers and /health endpoint safety."""
        res = client.post("/api/chat?stream=true", json={"question": "ping"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/event-stream", res.headers.get("content-type", ""))
        self.assertEqual(res.headers.get("x-accel-buffering"), "no")

        res_health = client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        for key in ["AIza", "nvapi-", "sk-"]:
            self.assertNotIn(key, res_health.text)


if __name__ == "__main__":
    unittest.main()
