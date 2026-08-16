"""
services/pdf_service.py
Document text extraction and chunking service for SS SPARK.

Supports:
- PDF (.pdf) via PyMuPDF (fitz)
- Word documents (.docx, .doc) via python-docx
- Plain text (.txt, .bib, .md)
- PowerPoint presentations (.pptx) via python-pptx
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

logger = logging.getLogger("ss_spark.pdf_service")


@dataclass
class TextChunk:
    text: str
    page: int
    chunk_index: int
    doc_id: str


def count_pdf_pages(file_path: str) -> int:
    """Return the total number of pages in a document file."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            count = len(doc)
            doc.close()
            return count
        except Exception as exc:
            logger.warning("Could not count PDF pages via PyMuPDF: %s", exc)
            return 1
    elif suffix == ".pptx":
        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            return len(prs.slides)
        except Exception:
            return 1
    return 1


def _split_into_chunks(
    text: str,
    page: int,
    doc_id: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[TextChunk]:
    """Split text into overlapping token/character windows."""
    words = text.split()
    if not words:
        return []

    chunks: List[TextChunk] = []
    start = 0
    chunk_idx = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text = " ".join(words[start:end]).strip()
        if chunk_text:
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    page=page,
                    chunk_index=chunk_idx,
                    doc_id=doc_id,
                )
            )
            chunk_idx += 1
        start += chunk_size - overlap
        if start >= len(words) or chunk_size <= overlap:
            break

    return chunks


def extract_chunks(
    file_path: str,
    doc_id: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[TextChunk]:
    """
    Extract text and chunk metadata from any supported document format.
    """
    path = Path(file_path)
    if not path.exists():
        logger.error("File does not exist: %s", file_path)
        return []

    suffix = path.suffix.lower()
    chunks: List[TextChunk] = []

    # 1. PDF Documents
    if suffix == ".pdf":
        try:
            import fitz
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text").strip()
                if text:
                    page_chunks = _split_into_chunks(
                        text=text,
                        page=page_num + 1,
                        doc_id=doc_id,
                        chunk_size=chunk_size,
                        overlap=overlap,
                    )
                    chunks.extend(page_chunks)
            doc.close()
        except Exception as exc:
            logger.error("Failed to parse PDF %s: %s", file_path, exc)

    # 2. Word Documents (.docx)
    elif suffix in (".docx", ".doc"):
        try:
            import docx
            doc = docx.Document(file_path)
            full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            chunks.extend(
                _split_into_chunks(
                    text=full_text,
                    page=1,
                    doc_id=doc_id,
                    chunk_size=chunk_size,
                    overlap=overlap,
                )
            )
        except Exception as exc:
            logger.error("Failed to parse DOCX %s: %s", file_path, exc)

    # 3. PowerPoint Presentations (.pptx)
    elif suffix == ".pptx":
        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            for idx, slide in enumerate(prs.slides, start=1):
                slide_text = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_text.append(shape.text.strip())
                if slide_text:
                    chunks.extend(
                        _split_into_chunks(
                            text="\n".join(slide_text),
                            page=idx,
                            doc_id=doc_id,
                            chunk_size=chunk_size,
                            overlap=overlap,
                        )
                    )
        except Exception as exc:
            logger.error("Failed to parse PPTX %s: %s", file_path, exc)

    # 4. Text & Markdown Files (.txt, .md, .bib, etc.)
    else:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                chunks.extend(
                    _split_into_chunks(
                        text=text,
                        page=1,
                        doc_id=doc_id,
                        chunk_size=chunk_size,
                        overlap=overlap,
                    )
                )
        except Exception as exc:
            logger.error("Failed to read text file %s: %s", file_path, exc)

    logger.info("Extracted %d chunks from %s", len(chunks), path.name)
    return chunks
