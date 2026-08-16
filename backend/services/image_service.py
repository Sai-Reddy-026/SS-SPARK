"""
services/image_service.py
OCR and Image Processing service for SS SPARK question paper images.

Supports:
- PNG, JPG, JPEG, WEBP question paper photos & scanned exam papers
- OCR text extraction with pytesseract & PIL
- OCR sidecar text generation for caching
- Seamless chunking for vector store ingestion
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

from services.pdf_service import TextChunk, _split_into_chunks

logger = logging.getLogger("ss_spark.image_service")


def extract_text_from_image(image_path: str) -> str:
    """
    Run OCR on an image file using pytesseract.
    Returns extracted text string, or empty string if OCR fails / is unavailable.
    """
    try:
        from PIL import Image
        import pytesseract

        img = Image.open(image_path)
        # Convert RGBA / palette images to RGB for OCR compatibility
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")

        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as exc:
        logger.warning("OCR processing skipped/failed on %s: %s", image_path, exc)
        return ""


def process_image_to_chunks(
    image_path: str,
    doc_id: str,
    upload_dir: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> Tuple[str, List[TextChunk]]:
    """
    Perform OCR on an image, write a `.ocr.txt` sidecar, and split into TextChunks.
    Returns (extracted_text, chunks).
    """
    img_path = Path(image_path)
    sidecar_path = img_path.parent / f"{img_path.stem}_ocr.txt"

    # Check if sidecar already exists
    if sidecar_path.exists():
        extracted_text = sidecar_path.read_text(encoding="utf-8", errors="ignore").strip()
    else:
        extracted_text = extract_text_from_image(image_path)
        if extracted_text:
            try:
                sidecar_path.write_text(extracted_text, encoding="utf-8")
            except Exception as exc:
                logger.warning("Could not write OCR sidecar file: %s", exc)

    if not extracted_text:
        extracted_text = f"[Image Document: {img_path.name} — OCR could not detect readable text]"

    chunks = _split_into_chunks(
        text=extracted_text,
        page=1,
        doc_id=doc_id,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    return extracted_text, chunks
