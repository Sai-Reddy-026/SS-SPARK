"""
services/image_service.py
Advanced OCR and Image Processing service for SS SPARK question paper images, scans, and diagrams.

Key Features:
- EXIF orientation correction (phone camera rotation fix)
- Intelligent adaptive preprocessing (DPI upscaling, contrast normalization, sharpening, grayscale)
- Multi-layout Tesseract OCR (PSM 3 automatic, PSM 6 uniform block, PSM 11 sparse diagram labels)
- Word confidence scoring and multi-configuration quality selection
- Structure-preserving text extraction (preserves newlines, tables, question numbering, formulas)
- Clean failure handling (zero vector DB contamination with fake text)
- Resilient sidecar caching with validation
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ss_spark.image_service")


def get_tesseract_cmd() -> Optional[str]:
    """Check if Tesseract binary is accessible in environment or standard paths."""
    try:
        import pytesseract
        # If explicitly configured in environment
        env_cmd = os.getenv("TESSERACT_CMD", "").strip()
        if env_cmd and Path(env_cmd).exists():
            pytesseract.pytesseract.tesseract_cmd = env_cmd
            return env_cmd

        # Check standard Windows paths if on Windows
        if os.name == "nt":
            std_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"C:\Users\AppData\Local\Tesseract-OCR\tesseract.exe",
            ]
            for p in std_paths:
                if Path(p).exists():
                    pytesseract.pytesseract.tesseract_cmd = p
                    return p

        # Test if available in system PATH
        pytesseract.get_tesseract_version()
        return "tesseract"
    except Exception:
        return None


def is_tesseract_available() -> bool:
    """Return True if Tesseract OCR engine is installed and ready."""
    return get_tesseract_cmd() is not None


def preprocess_image_for_ocr(img: Any) -> Any:
    """
    Intelligent adaptive image preprocessor for question papers, scans, and screenshots:
      1. Corrects EXIF camera orientation (phone camera photos)
      2. Upscales low-resolution images (<1500px) using high-quality Lanczos resampling
      3. Converts to grayscale and normalizes contrast (autocontrast)
      4. Applies mild sharpening to enhance character edge clarity
      5. Handles dark/inverted backgrounds
    """
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat

    # 1. Correct EXIF camera orientation (crucial for smartphone uploads)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception as exc:
        logger.debug("EXIF transposition skipped: %s", exc)

    # 2. Ensure RGB mode
    if img.mode not in ("L", "RGB"):
        img = img.convert("RGB")

    w, h = img.size

    # 3. High-quality upscale if dimensions are small (standard screenshots have 72-96 DPI; Tesseract needs ~300 DPI)
    min_dimension = min(w, h)
    max_dimension = max(w, h)
    if max_dimension < 1800 or min_dimension < 1000:
        scale_factor = max(1.5, min(3.0, 2000.0 / float(max_dimension or 1)))
        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)
        img = img.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)

    # 4. Grayscale conversion
    gray = img.convert("L")

    # 5. Check if background is dark/inverted (light text on dark background)
    stat = ImageStat.Stat(gray)
    mean_val = stat.mean[0] if stat.mean else 128
    if mean_val < 90:
        # Invert to standard dark-text-on-light-background
        gray = ImageOps.invert(gray)

    # 6. Adaptive contrast normalization
    gray = ImageOps.autocontrast(gray, cutoff=1)

    # 7. Mild unsharp masking to enhance character edges without adding noise
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=140, threshold=3))

    return gray


def extract_text_with_confidence(
    image: Any,
    lang: Optional[str] = None,
) -> Tuple[str, float, bool]:
    """
    Run multi-layout Tesseract OCR on a PIL Image object.
    
    Returns:
      (extracted_text: str, confidence_pct: float, success: bool)
    """
    try:
        from PIL import Image
        import pytesseract

        if not is_tesseract_available():
            logger.warning("Tesseract OCR is not installed or not in system PATH. OCR skipped.")
            return "", 0.0, False

        ocr_lang = lang or os.getenv("OCR_LANG", "eng").strip() or "eng"
        try:
            available_langs = pytesseract.get_languages(config="")
            requested = [r.strip() for r in ocr_lang.split("+") if r.strip()]
            valid_parts = [r for r in requested if r in available_langs]
            if valid_parts:
                ocr_lang = "+".join(valid_parts)
            elif "eng" in available_langs:
                ocr_lang = "eng"
        except Exception:
            pass

        # Preprocess PIL image
        proc_img = preprocess_image_for_ocr(image)

        # Multi-layout configurations to evaluate
        configs = [
            ("--oem 3 --psm 3", "PSM 3 (Auto Page Segmentation)"),
            ("--oem 3 --psm 6", "PSM 6 (Uniform Block / Dense Exam Page)"),
            ("--oem 3 --psm 11", "PSM 11 (Sparse Text / Diagram Labels)"),
        ]

        best_text = ""
        best_conf = 0.0

        for cfg_args, label in configs:
            try:
                # 1. Run image_to_data for confidence analysis
                data = pytesseract.image_to_data(
                    proc_img,
                    lang=ocr_lang,
                    config=cfg_args,
                    output_type=pytesseract.Output.DICT,
                )

                confs = [int(c) for c in data.get("conf", []) if str(c).lstrip("-").isdigit() and int(c) >= 0]
                avg_conf = (sum(confs) / len(confs)) if confs else 0.0

                # 2. Run image_to_string for structural text with linebreaks
                raw_text = pytesseract.image_to_string(
                    proc_img,
                    lang=ocr_lang,
                    config=cfg_args,
                ).strip()

                # Clean non-printable control characters while preserving \n, \t, punctuation
                cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw_text)

                char_count = len(re.sub(r"\s+", "", cleaned))
                if char_count > 0 and (avg_conf > best_conf or (best_conf < 40 and char_count > len(best_text))):
                    best_text = cleaned
                    best_conf = avg_conf

                # If primary PSM 3 gives high confidence, stop early for fast performance
                if best_conf >= 65.0 and char_count >= 30:
                    break

            except Exception as psm_err:
                logger.debug("OCR attempt with %s failed: %s", label, psm_err)
                continue

        success = bool(best_text.strip()) and best_conf > 0.0
        return best_text.strip(), round(best_conf, 2), success

    except Exception as exc:
        logger.warning("OCR processing error: %s", exc)
        return "", 0.0, False


def extract_text_from_image(image_path: str, lang: Optional[str] = None) -> str:
    """
    Run high-quality OCR on an image file path.
    Returns extracted text string, or empty string if OCR fails.
    """
    path = Path(image_path)
    if not path.exists():
        logger.error("Image file not found: %s", image_path)
        return ""

    try:
        from PIL import Image
        with Image.open(str(path)) as img:
            text, conf, success = extract_text_with_confidence(img, lang=lang)
            if success:
                logger.info("OCR extracted %d characters (conf: %.1f%%) from '%s'", len(text), conf, path.name)
            return text
    except Exception as exc:
        logger.warning("Could not open image '%s' for OCR: %s", image_path, exc)
        return ""


def process_image_to_chunks(
    image_path: str,
    doc_id: str,
    upload_dir: str,
    chunk_size: int = 500,
    overlap: int = 50,
    lang: Optional[str] = None,
) -> Tuple[str, List[Any], Dict[str, Any]]:
    """
    Perform OCR on an image, write/validate sidecars, and generate structured TextChunks.
    
    Returns:
      (extracted_text: str, chunks: List[TextChunk], ocr_metadata: Dict[str, Any])
    """
    from services.pdf_service import _split_into_structured_chunks, TextChunk

    img_path = Path(image_path)
    sidecar_path = img_path.parent / f"{img_path.stem}_ocr.txt"
    meta_path = img_path.parent / f"{img_path.stem}_ocr.json"

    extracted_text = ""
    ocr_conf = 0.0
    ocr_success = False

    # 1. Check existing sidecar cache
    if sidecar_path.exists():
        cached_text = sidecar_path.read_text(encoding="utf-8", errors="ignore").strip()
        # Ensure cached text is not old fake failure placeholder
        if cached_text and not cached_text.startswith("[Image Document:"):
            extracted_text = cached_text
            ocr_success = True
            if meta_path.exists():
                try:
                    meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
                    ocr_conf = float(meta_data.get("confidence", 85.0))
                except Exception:
                    ocr_conf = 85.0
            logger.debug("Loaded OCR text from sidecar cache for '%s'", img_path.name)

    # 2. Extract fresh OCR if not cached
    if not extracted_text:
        try:
            from PIL import Image
            with Image.open(str(img_path)) as img:
                extracted_text, ocr_conf, ocr_success = extract_text_with_confidence(img, lang=lang)
        except Exception as exc:
            logger.warning("OCR execution failed for '%s': %s", img_path.name, exc)
            extracted_text = ""
            ocr_conf = 0.0
            ocr_success = False

        # Write sidecar files if text was successfully extracted
        if extracted_text and ocr_success:
            try:
                sidecar_path.write_text(extracted_text, encoding="utf-8")
                meta_path.write_text(
                    json.dumps({
                        "filename": img_path.name,
                        "confidence": ocr_conf,
                        "success": True,
                        "char_count": len(extracted_text),
                    }),
                    encoding="utf-8",
                )
            except Exception as sidecar_err:
                logger.warning("Failed to write OCR sidecar for '%s': %s", img_path.name, sidecar_err)

    # 3. Build structured text chunks
    chunks: List[TextChunk] = []
    if extracted_text and ocr_success:
        chunks = _split_into_structured_chunks(
            text=extracted_text,
            page=1,
            doc_id=doc_id,
            chunk_size=chunk_size,
            overlap=overlap,
            is_ocr=True,
            source=img_path.name,
        )

    metadata: Dict[str, Any] = {
        "extraction_method": "ocr",
        "ocr_success": ocr_success,
        "ocr_confidence": ocr_conf,
        "char_count": len(extracted_text),
        "chunk_count": len(chunks),
        "filename": img_path.name,
    }

    return extracted_text, chunks, metadata
