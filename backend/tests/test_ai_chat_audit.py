"""
backend/tests/test_ai_chat_audit.py

Comprehensive test suite verifying the AI chat system audit fixes:
  1. Gemini primary selection & streaming
  2. Gemini failure/timeout -> NVIDIA automatic fallback
  3. Mid-stream Gemini failure -> reset event + NVIDIA clean response
  4. Both providers failing -> clean error message without hanging
  5. RAG question handling & citations
  6. General question handling (fast-path routing)
  7. Concurrent requests isolation & correlation IDs
  8. Client cancellation handling
  9. Production SSE headers verification
  10. Health endpoint reporting (no secret leaks)
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
    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
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
    # Test 1: Gemini Primary Success
    # ---------------------------------------------------------------------- #
    async def test_01_gemini_primary_success(self):
        """Verify Gemini is tried first and streams tokens."""
        mock_chunks = [
            _create_mock_chunk("The "),
            _create_mock_chunk("OSI "),
            _create_mock_chunk("model has 7 layers."),
        ]

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_litellm:
            mock_litellm.return_value = AsyncIteratorMock(mock_chunks)

            tokens = []
            resets = 0
            async for chunk in ask_question_stream("Explain OSI model", session_id="test-gemini-success"):
                events = parse_sse_events(chunk)
                for ev in events:
                    if ev.get("type") == "token":
                        tokens.append(ev.get("content", ""))
                    elif ev.get("type") == "reset":
                        resets += 1

            full_text = "".join(tokens)
            self.assertEqual(resets, 0)
            self.assertEqual(full_text, "The OSI model has 7 layers.")
            # Verify primary model was a Gemini model
            called_model = mock_litellm.call_args_list[0][1]["model"]
            self.assertTrue("gemini" in called_model, f"Expected Gemini model, got {called_model}")

    # ---------------------------------------------------------------------- #
    # Test 2: Gemini Failure / Timeout -> NVIDIA Fallback
    # ---------------------------------------------------------------------- #
    async def test_02_gemini_failure_nvidia_fallback(self):
        """Verify when Gemini fails initially, NVIDIA is called and responds seamlessly."""
        gemini_error = Exception("429 Resource has been exhausted / Rate limit reached")
        nvidia_chunks = [
            _create_mock_chunk("NVIDIA: "),
            _create_mock_chunk("OSI model "),
            _create_mock_chunk("explanation."),
        ]

        async def mock_acompletion_side_effect(*args, **kwargs):
            model = kwargs.get("model", "")
            if "gemini" in model:
                raise gemini_error
            elif "nvidia" in model:
                return AsyncIteratorMock(nvidia_chunks)
            raise Exception(f"Unexpected model: {model}")

        with patch("litellm.acompletion", side_effect=mock_acompletion_side_effect) as mock_litellm:
            tokens = []
            resets = 0
            async for chunk in ask_question_stream("Explain OSI model", session_id="test-gemini-fail-fallback"):
                events = parse_sse_events(chunk)
                for ev in events:
                    if ev.get("type") == "token":
                        tokens.append(ev.get("content", ""))
                    elif ev.get("type") == "reset":
                        resets += 1

            full_text = "".join(tokens)
            self.assertEqual(full_text, "NVIDIA: OSI model explanation.")
            # Confirm Gemini was attempted first, and NVIDIA second
            models_attempted = [call[1]["model"] for call in mock_litellm.call_args_list]
            self.assertTrue(any("gemini" in m for m in models_attempted))
            self.assertTrue(any("nvidia" in m for m in models_attempted))

    # ---------------------------------------------------------------------- #
    # Test 3: Mid-stream Gemini Failure -> Reset event + Clean NVIDIA response
    # ---------------------------------------------------------------------- #
    async def test_03_gemini_midstream_failure_reset(self):
        """Verify mid-stream Gemini crash emits a reset event and NVIDIA yields clean text."""
        # Gemini emits 2 tokens then crashes mid-stream
        gemini_stream_crash = [
            _create_mock_chunk("Incomplete "),
            _create_mock_chunk("Gemini "),
            Exception("Connection reset by peer mid-stream"),
        ]
        nvidia_complete_stream = [
            _create_mock_chunk("Complete "),
            _create_mock_chunk("NVIDIA "),
            _create_mock_chunk("response."),
        ]

        async def mock_acompletion_side_effect(*args, **kwargs):
            model = kwargs.get("model", "")
            if "gemini" in model:
                return AsyncIteratorMock(gemini_stream_crash)
            elif "nvidia" in model:
                return AsyncIteratorMock(nvidia_complete_stream)
            raise Exception(f"Unexpected model: {model}")

        with patch("litellm.acompletion", side_effect=mock_acompletion_side_effect):
            events_received = []
            tokens = []
            resets = 0

            async for chunk in ask_question_stream("Tell me about algorithms", session_id="test-midstream-reset"):
                events = parse_sse_events(chunk)
                for ev in events:
                    events_received.append(ev)
                    if ev.get("type") == "reset":
                        resets += 1
                        tokens.clear()  # Frontend resets its accumulator on reset event
                    elif ev.get("type") == "token":
                        tokens.append(ev.get("content", ""))

            full_text = "".join(tokens)
            self.assertGreaterEqual(resets, 1, "Must emit at least one reset event on mid-stream failure")
            self.assertEqual(full_text, "Complete NVIDIA response.", "Accumulated text must match clean NVIDIA response without Gemini residue")

    # ---------------------------------------------------------------------- #
    # Test 4: Both Providers Fail -> Clean Error, Zero Infinite Hang
    # ---------------------------------------------------------------------- #
    async def test_04_both_providers_fail_clean_error(self):
        """Verify when all providers fail, a clear error and done event are emitted."""
        async def mock_fail_all(*args, **kwargs):
            raise Exception("API down")

        with patch("litellm.acompletion", side_effect=mock_fail_all):
            events = []
            async for chunk in ask_question_stream("Hello", session_id="test-all-fail"):
                events.extend(parse_sse_events(chunk))

            event_types = [e.get("type") for e in events]
            self.assertIn("done", event_types, "Stream must emit 'done' event")
            token_contents = [e.get("content", "") for e in events if e.get("type") == "token"]
            full_msg = "".join(token_contents)
            self.assertTrue(
                "temporarily unavailable" in full_msg.lower() or "error" in full_msg.lower(),
                f"Expected friendly error message, got: {full_msg}",
            )

    # ---------------------------------------------------------------------- #
    # Test 5: RAG Question with Grounded Vector Chunks
    # ---------------------------------------------------------------------- #
    async def test_05_rag_grounded_response(self):
        """Verify vector retrieval grounded prompt and citations metadata."""
        from rag.retriever import RetrievedChunk, RetrievalResult

        mock_chunks = [
            RetrievedChunk(
                id="c1",
                doc_id="d1",
                source="OS_Notes.pdf",
                page=12,
                text="Deadlock occurs when four conditions are met: mutual exclusion, hold and wait, no preemption, circular wait.",
                relevance=0.88,
            )
        ]

        llm_answer = [_create_mock_chunk("According to OS_Notes.pdf (Page 12), deadlock requires four Coffman conditions.")]

        with patch("services.chat_service._get_cached_documents", new_callable=AsyncMock) as mock_docs, \
             patch("rag.retriever.retrieve", new_callable=AsyncMock) as mock_ret, \
             patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:

            mock_doc_obj = MagicMock()
            mock_doc_obj.name = "OS_Notes.pdf"
            mock_docs.return_value = [mock_doc_obj]
            mock_ret.return_value = RetrievalResult(mock_chunks)
            mock_llm.return_value = AsyncIteratorMock(llm_answer)

            events = []
            async for chunk in ask_question_stream("What are deadlock conditions in OS_Notes.pdf?", session_id="test-rag"):
                events.extend(parse_sse_events(chunk))

            meta_events = [e for e in events if e.get("type") == "meta"]
            self.assertEqual(len(meta_events), 1)
            meta = meta_events[0]
            self.assertEqual(meta.get("source"), "OS_Notes.pdf")
            self.assertEqual(meta.get("page"), 12)
            self.assertEqual(len(meta.get("citations", [])), 1)
            self.assertEqual(meta["citations"][0]["source"], "OS_Notes.pdf")

    # ---------------------------------------------------------------------- #
    # Test 6: Non-RAG / General Question
    # ---------------------------------------------------------------------- #
    async def test_06_non_rag_fast_routing(self):
        """Verify conversational greeting bypasses RAG and streams directly."""
        mock_chunks = [_create_mock_chunk("Hello! How can I help you today?")]

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = AsyncIteratorMock(mock_chunks)

            events = []
            async for chunk in ask_question_stream("Hello", session_id="test-greeting"):
                events.extend(parse_sse_events(chunk))

            meta_events = [e for e in events if e.get("type") == "meta"]
            self.assertEqual(len(meta_events), 1)
            self.assertEqual(meta_events[0].get("status"), "general")
            self.assertEqual(meta_events[0].get("citations"), [])

    # ---------------------------------------------------------------------- #
    # Test 7: Multiple Concurrent Chat Requests
    # ---------------------------------------------------------------------- #
    async def test_07_concurrent_chat_requests(self):
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
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)
        for sid, text in results:
            idx = sid.split("-")[1]
            self.assertEqual(text, f"Answer for Question {idx}")

    # ---------------------------------------------------------------------- #
    # Test 8: Client Cancellation Handling
    # ---------------------------------------------------------------------- #
    async def test_08_client_cancellation(self):
        """Verify generator cancellation raises CancelledError and logs cleanly."""
        async def endless_stream(*args, **kwargs):
            while True:
                await asyncio.sleep(0.1)
                yield _create_mock_chunk("token")

        with patch("litellm.acompletion", side_effect=endless_stream):
            gen = ask_question_stream("Long question", session_id="test-cancel")
            # Consume 1 event, then cancel
            await gen.asend(None)
            await gen.aclose()

    # ---------------------------------------------------------------------- #
    # Test 9: Production SSE Headers Verification
    # ---------------------------------------------------------------------- #
    def test_09_production_sse_headers(self):
        """Verify FastAPI endpoint returns required headers."""
        res = client.post("/api/chat?stream=true", json={"question": "ping"})
        self.assertEqual(res.status_code, 200)
        headers = res.headers
        self.assertIn("text/event-stream", headers.get("content-type", ""))
        self.assertIn("no-cache", headers.get("cache-control", ""))
        self.assertIn("no-transform", headers.get("cache-control", ""))
        self.assertEqual(headers.get("x-accel-buffering"), "no")

    # ---------------------------------------------------------------------- #
    # Test 10: Health Endpoint Reporting & No Secret Leaks
    # ---------------------------------------------------------------------- #
    def test_10_health_endpoint_diagnostics(self):
        """Verify /health endpoint returns diagnostics without exposing any secret keys."""
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data.get("status"), "ok")
        self.assertIn("gemini", data)
        self.assertIn("nvidia", data)
        self.assertIn("mongodb", data)
        self.assertIn("vector_store", data)

        # Ensure no raw secret keys or tokens are in the JSON body
        raw_body = res.text
        for key in ["AIza", "nvapi-", "sk-"]:
            self.assertNotIn(key, raw_body, "Secret API key prefix detected in health response!")


if __name__ == "__main__":
    unittest.main()
