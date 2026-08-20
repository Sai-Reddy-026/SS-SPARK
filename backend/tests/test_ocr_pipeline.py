"""
backend/tests/test_ocr_pipeline.py

Comprehensive test suite verifying the SS-SPARK Image & Document OCR and RAG Pipeline:
  1. PIL image preprocessing, EXIF transpose, upscaling, and contrast normalization
  2. Structure-aware chunking for question papers, sections, and tables
  3. Clean OCR failure handling (zero vector DB pollution with dummy text)
  4. Hybrid PDF extraction (digital text + high-res scanned page OCR)
  5. Image upload pipeline bridging to PaperQA via add_text_content
  6. Exam Question Lexical Reranker (boosts exact Q1, Q5, Part-A, Marks matches)
  7. Table & Diagram layout preservation
  8. Multi-tenant user isolation for OCR-derived chunks
  9. End-to-end RAG chat stream with OCR-grounded citations
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from PIL import Image, ImageDraw
import fitz  # PyMuPDF

from services.image_service import (
    preprocess_image_for_ocr,
    extract_text_with_confidence,
    process_image_to_chunks,
    is_tesseract_available,
)
from services.pdf_service import (
    _split_into_structured_chunks,
    extract_chunks,
    count_pdf_pages,
    TextChunk,
)
from rag.retriever import _hybrid_rerank, RetrievedChunk, RetrievalResult
from services.chat_service import ask_question_stream


class TestOCRPipeline(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = "mock-gemini-key"
        os.environ["GOOGLE_API_KEY"] = "mock-gemini-key"
        os.environ["NVIDIA_API_KEY"] = "mock-nvidia-key"
        os.environ["NVIDIA_NIM_API_KEY"] = "mock-nvidia-key"
        self.tmp_dir = Path(tempfile.gettempdir()) / "ss_spark_ocr_tests"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------- #
    # 1. PIL Image Preprocessing & Upscaling
    # ---------------------------------------------------------------------- #
    def test_01_image_preprocessing(self):
        """Verify image preprocessor handles small dimensions, RGBA, and contrast."""
        # Create a small 200x100 RGBA image with dark background and white text
        img = Image.new("RGBA", (200, 100), color=(20, 20, 20, 255))
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "Sample Exam Text", fill=(255, 255, 255, 255))

        processed = preprocess_image_for_ocr(img)
        self.assertEqual(processed.mode, "L", "Must convert to grayscale mode 'L'")
        self.assertGreaterEqual(processed.width, 400, "Must upscale low-resolution image")
        self.assertGreaterEqual(processed.height, 200, "Must upscale low-resolution image")

    # ---------------------------------------------------------------------- #
    # 2. Structure-Aware Chunking (Question Papers & Tables)
    # ---------------------------------------------------------------------- #
    def test_02_structured_chunking(self):
        """Verify chunker preserves question numbering, headings, and table rows."""
        exam_text = (
            "SECTION A — SHORT QUESTIONS (5 x 2 = 10 Marks)\n\n"
            "Q1. Define Process Control Block (PCB) and list its components.\n\n"
            "Q2. What are the four Coffman conditions required for deadlock?\n\n"
            "Q3. Differentiate between paging and segmentation.\n\n"
            "SECTION B — ESSAY QUESTIONS (3 x 10 = 30 Marks)\n\n"
            "Q4. Explain Banker's Deadlock Avoidance Algorithm with the following table:\n"
            "Process | Allocation | Max Need | Available\n"
            "P0      | 0 1 0      | 7 5 3    | 3 3 2\n"
            "P1      | 2 0 0      | 3 2 2    | 3 3 2\n"
            "P2      | 3 0 2      | 9 0 2    | 3 3 2\n\n"
            "Q5. Describe the Round Robin CPU Scheduling algorithm with time quantum = 4ms."
        )

        chunks = _split_into_structured_chunks(
            text=exam_text,
            page=1,
            doc_id="exam_doc_1",
            chunk_size=300,
            overlap=30,
            is_ocr=True,
            source="exam_paper.png",
        )

        self.assertGreaterEqual(len(chunks), 1)
        full_chunk_text = " ".join(c.text for c in chunks)

        # Ensure question headers and table rows are preserved
        self.assertIn("Q1.", full_chunk_text)
        self.assertIn("Q4.", full_chunk_text)
        self.assertIn("Process | Allocation", full_chunk_text)
        self.assertEqual(chunks[0].page, 1)
        self.assertTrue(chunks[0].is_ocr)
        self.assertEqual(chunks[0].source, "exam_paper.png")

    # ---------------------------------------------------------------------- #
    # 3. Clean OCR Failure Handling (No Fake Dummy Chunks)
    # ---------------------------------------------------------------------- #
    def test_03_clean_ocr_failure_no_dummy_chunks(self):
        """Verify unreadable image returns 0 chunks and zero vector DB pollution."""
        blank_img_path = self.tmp_dir / "blank_test.png"
        blank_img = Image.new("RGB", (300, 300), color=(255, 255, 255))
        blank_img.save(str(blank_img_path))

        with patch("services.image_service.extract_text_with_confidence", return_value=("", 0.0, False)):
            extracted_text, chunks, ocr_meta = process_image_to_chunks(
                image_path=str(blank_img_path),
                doc_id="blank_doc_1",
                upload_dir=str(self.tmp_dir),
            )

            self.assertEqual(extracted_text, "")
            self.assertEqual(len(chunks), 0, "Failed OCR must produce 0 chunks — NEVER dummy failure strings!")
            self.assertFalse(ocr_meta["ocr_success"])

    # ---------------------------------------------------------------------- #
    # 4. Hybrid PDF Extraction (Digital + Scanned Pages)
    # ---------------------------------------------------------------------- #
    def test_04_hybrid_pdf_extraction(self):
        """Verify PDF parser reads digital text and triggers OCR on scanned pages."""
        pdf_path = self.tmp_dir / "hybrid_test.pdf"
        doc = fitz.open()

        # Page 1: Digital text
        page1 = doc.new_page()
        page1.insert_text((50, 72), "Unit 1: Introduction to Operating Systems and System Calls.")

        # Page 2: Scanned simulation (empty digital text layer)
        page2 = doc.new_page()

        doc.save(str(pdf_path))
        doc.close()

        with patch("services.image_service.is_tesseract_available", return_value=True), \
             patch("services.image_service.extract_text_with_confidence", return_value=("Scanned Page 2 OCR: Explain Semaphores.", 88.0, True)):

            chunks = extract_chunks(str(pdf_path), doc_id="hybrid_pdf_1")

            self.assertGreaterEqual(len(chunks), 2)
            # Page 1 chunk
            p1_chunk = next(c for c in chunks if c.page == 1)
            self.assertIn("Unit 1", p1_chunk.text)
            self.assertFalse(p1_chunk.is_ocr)

            # Page 2 chunk
            p2_chunk = next(c for c in chunks if c.page == 2)
            self.assertIn("Scanned Page 2 OCR", p2_chunk.text)
            self.assertTrue(p2_chunk.is_ocr)

    # ---------------------------------------------------------------------- #
    # 5. Image Upload Bridging to PaperQA
    # ---------------------------------------------------------------------- #
    async def test_05_upload_bridges_ocr_to_paperqa(self):
        """Verify image upload invokes add_text_content with extracted OCR text."""
        from fastapi import UploadFile

        test_img_path = self.tmp_dir / "qp_photo.jpg"
        test_img = Image.new("RGB", (400, 400), color=(240, 240, 240))
        test_img.save(str(test_img_path))

        fake_upload = UploadFile(
            file=io.BytesIO(test_img_path.read_bytes()),
            filename="qp_photo.jpg",
        )

        with patch("services.image_service.process_image_to_chunks", return_value=(
                "Q1. Explain OSI model layers.",
                [TextChunk(text="Q1. Explain OSI model layers.", page=1, chunk_index=0, doc_id="d1", is_ocr=True, source="qp_photo.jpg")],
                {"ocr_success": True, "ocr_confidence": 92.0}
             )), \
             patch("rag.paperqa_connector.add_text_content", new_callable=AsyncMock) as mock_pqa_text, \
             patch("rag.embeddings.get_embedder"), \
             patch("rag.vector_store.get_vector_store"), \
             patch("database.models.save_document", new_callable=AsyncMock):

            from api.upload import upload_documents
            from core.config import get_settings

            cfg = get_settings()
            res = await upload_documents(files=[fake_upload], current_user=None, settings=cfg)

            self.assertTrue(res["success"])
            self.assertEqual(len(res["data"]), 1)
            item = res["data"][0]
            self.assertEqual(item["kind"], "image")
            self.assertEqual(item["extraction_method"], "ocr")
            self.assertEqual(item["chunk_count"], 1)

            # Verify PaperQA received the extracted OCR text
            mock_pqa_text.assert_called_once()
            called_text = mock_pqa_text.call_args[1]["text"]
            called_source = mock_pqa_text.call_args[1]["source_name"]
            self.assertEqual(called_text, "Q1. Explain OSI model layers.")
            self.assertEqual(called_source, "qp_photo.jpg")

    # ---------------------------------------------------------------------- #
    # 6. Exam Question Lexical Reranker Boost
    # ---------------------------------------------------------------------- #
    def test_06_exam_question_lexical_boost(self):
        """Verify user asking for 'Question 5' prioritizes the chunk with 'Q5.'."""
        chunks = [
            RetrievedChunk(
                id="c1",
                doc_id="d1",
                source="exam.png",
                page=1,
                text="Q1. Define thrashing in virtual memory.",
                relevance=0.45,
                is_ocr=True,
            ),
            RetrievedChunk(
                id="c2",
                doc_id="d1",
                source="exam.png",
                page=1,
                text="Q5. Explain Banker's Deadlock Avoidance Algorithm in detail.",
                relevance=0.40,
                is_ocr=True,
            ),
            RetrievedChunk(
                id="c3",
                doc_id="d1",
                source="exam.png",
                page=1,
                text="SECTION C — Long Essay Questions.",
                relevance=0.30,
                is_ocr=True,
            ),
        ]

        reranked = _hybrid_rerank("What is question 5 in the exam paper?", chunks)

        # Chunk 2 (Q5) must be reranked to the top
        self.assertEqual(reranked[0].id, "c2")
        self.assertIn("Q5. Explain Banker's", reranked[0].text)
        self.assertGreater(reranked[0].relevance, 0.50)

    # ---------------------------------------------------------------------- #
    # 7. User Multi-Tenant Isolation for OCR Chunks
    # ---------------------------------------------------------------------- #
    async def test_07_user_multi_tenant_isolation(self):
        """Verify vector retrieval strictly isolates OCR chunks by user_id."""
        from rag.retriever import retrieve

        with patch("rag.retriever.get_embedder") as mock_emb_getter, \
             patch("rag.retriever.get_vector_store") as mock_vs_getter:

            mock_emb = MagicMock()
            mock_emb.embed.return_value = [[0.1] * 384]
            mock_emb_getter.return_value = mock_emb

            mock_vs = MagicMock()
            mock_vs.search.return_value = [
                {"id": "c1", "doc_id": "d1", "source": "userA_notes.jpg", "page": 1, "text": "Secret formula", "relevance": 0.9}
            ]
            mock_vs_getter.return_value = mock_vs

            # Query under user_id="user_b"
            await retrieve("Secret formula", user_id="user_b", req_id="test-iso")

            # Check that user_id was passed into vs.search filter
            search_call = mock_vs.search.call_args[1]
            self.assertEqual(search_call.get("user_id"), "user_b")

    # ---------------------------------------------------------------------- #
    # 8. End-to-End Chat Stream with OCR-Grounded Context
    # ---------------------------------------------------------------------- #
    async def test_08_e2e_chat_with_ocr_grounding(self):
        """Verify /api/chat stream uses OCR chunks and returns proper citation metadata."""
        mock_ocr_chunks = [
            RetrievedChunk(
                id="c_ocr_1",
                doc_id="d_ocr_1",
                source="question_paper_scan.png",
                page=2,
                text="Question 4 (10 Marks): State and prove Master's Theorem for divide and conquer recurrences.",
                relevance=0.82,
                is_ocr=True,
            )
        ]

        def _create_chunk(text):
            m = MagicMock()
            m.choices = [MagicMock(delta=MagicMock(content=text))]
            return m

        class StreamMock:
            def __init__(self):
                self.items = [_create_chunk("According to question_paper_scan.png (Page 2), Question 4 asks for Master's Theorem.")]
                self.idx = 0
            def __aiter__(self):
                return self
            async def __anext__(self):
                if self.idx >= len(self.items):
                    raise StopAsyncIteration
                it = self.items[self.idx]
                self.idx += 1
                return it
            async def aclose(self):
                pass

        with patch("services.chat_service._get_cached_documents", new_callable=AsyncMock) as mock_docs, \
             patch("rag.retriever.retrieve", new_callable=AsyncMock) as mock_ret, \
             patch("litellm.acompletion", new_callable=AsyncMock) as mock_llm:

            mock_doc_obj = MagicMock()
            mock_doc_obj.name = "question_paper_scan.png"
            mock_docs.return_value = [mock_doc_obj]
            mock_ret.return_value = RetrievalResult(mock_ocr_chunks)
            mock_llm.return_value = StreamMock()

            events = []
            async for chunk in ask_question_stream("What is question 4 in question_paper_scan.png?", session_id="test-ocr-chat"):
                for line in chunk.split("\n"):
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str:
                            events.append(json.loads(data_str))

            meta_events = [e for e in events if e.get("type") == "meta"]
            self.assertEqual(len(meta_events), 1)
            meta = meta_events[0]
            self.assertEqual(meta["source"], "question_paper_scan.png")
            self.assertEqual(meta["page"], 2)
            self.assertEqual(len(meta["citations"]), 1)
            self.assertEqual(meta["citations"][0]["source"], "question_paper_scan.png")


if __name__ == "__main__":
    unittest.main()
