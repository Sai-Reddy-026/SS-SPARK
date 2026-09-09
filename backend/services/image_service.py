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


def preprocess_image_for_vision(img: Any) -> Any:
    """Prepare PIL image for Gemini Vision: fix EXIF orientation, bound maximum dimension to 3000px."""
    from PIL import Image, ImageOps
    try:
        img = ImageOps.exif_transpose(img)
    except Exception as exc:
        logger.debug("EXIF transposition skipped in vision prep: %s", exc)

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    w, h = img.size
    max_dim = max(w, h)
    if max_dim > 3000:
        scale = 3000.0 / float(max_dim)
        img = img.resize((int(w * scale), int(h * scale)), resample=Image.Resampling.LANCZOS)
    elif max_dim < 1200:
        scale = min(2.5, 1800.0 / float(max_dim or 1))
        img = img.resize((int(w * scale), int(h * scale)), resample=Image.Resampling.LANCZOS)
    return img


def _parse_json_from_llm(raw: str) -> Optional[Dict[str, Any]]:
    """Parse JSON dictionary safely from LLM output, extracting from markdown code blocks or brackets."""
    if not raw:
        return None
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    try:
        return json.loads(raw)
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except Exception:
            pass
    return None


def _get_gemini_api_key() -> str:
    """Retrieve Gemini API key from settings or environment."""
    try:
        from core.config import get_settings
        key = get_settings().GEMINI_API_KEY
        if key:
            return key.strip()
    except Exception:
        pass
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


def extract_structured_question_paper(
    image_path: str,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Extract structured question paper content using Google Gemini Multimodal Vision.
    Extracts exam title, sections, questions with numbers, options, marks, diagrams, and LaTeX math.
    """
    path = Path(image_path)
    if not path.exists():
        logger.error("Image file not found: %s", image_path)
        return "", [], {"success": False, "method": "none", "confidence": 0.0}

    from PIL import Image
    import google.generativeai as genai
    gemini_key = _get_gemini_api_key()
    if not gemini_key:
        logger.warning("GEMINI_API_KEY not configured for visual question extraction.")
        return "", [], {"success": False, "method": "none", "confidence": 0.0}

    try:
        genai.configure(api_key=gemini_key)
        with Image.open(str(path)) as raw_img:
            pil_img = preprocess_image_for_vision(raw_img)

        prompt = (
            "You are an expert academic document and question paper analyzer.\n"
            "Carefully read and analyze this question paper / exam / study document image.\n"
            "Extract every question, section, and problem with maximum precision.\n"
            "Preserve:\n"
            "1. Question numbers exactly as written (e.g. Q1, Q2, Question 3, 4(a)).\n"
            "2. Section/Part headings (e.g. SECTION A, Part II).\n"
            "3. Marks allotted (e.g. 5 Marks, [10M]).\n"
            "4. MCQs and all options ((A), (B), (C), (D)).\n"
            "5. Mathematical, physics, and chemical expressions in clean LaTeX (use $...$ for inline and $$...$$ for block).\n"
            "6. Explicitly note and describe any diagrams, graphs, circuits, or tables visible.\n\n"
            "Return ONLY a JSON object with this exact schema:\n"
            "{\n"
            '  "title": "Title or subject of paper",\n'
            '  "sections": ["SECTION A", ...],\n'
            '  "full_text": "Complete transcribed markdown text of the document",\n'
            '  "questions": [\n'
            '    {\n'
            '      "q_num": "Q1",\n'
            '      "section": "SECTION A",\n'
            '      "marks": "5 Marks",\n'
            '      "text": "Full text of the question...",\n'
            '      "options": ["(A)...", "(B)..."],\n'
            '      "has_diagram": false,\n'
            '      "diagram_description": ""\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "If there are no explicit question numbers, extract the problems or paragraphs into the questions list with q_num 'Q1', 'Q2', etc."
        )

        models_to_try = ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash"]
        for m_name in models_to_try:
            try:
                model = genai.GenerativeModel(m_name)
                logger.info("Extracting structured questions from '%s' via %s", path.name, m_name)
                res = model.generate_content([prompt, pil_img])
                data = _parse_json_from_llm(res.text)
                if data and isinstance(data, dict):
                    full_text = data.get("full_text", "").strip()
                    questions = data.get("questions", [])
                    if not full_text and questions:
                        parts = []
                        if data.get("title"):
                            parts.append(f"# {data['title']}\n")
                        for q in questions:
                            parts.append(f"### {q.get('q_num', '')} ({q.get('marks', '')})\n{q.get('text', '')}")
                        full_text = "\n\n".join(parts)
                    meta = {
                        "success": True,
                        "method": "vision",
                        "confidence": 96.0,
                        "title": data.get("title", ""),
                        "sections": data.get("sections", []),
                        "question_count": len(questions),
                    }
                    logger.info("Vision extracted %d questions and %d chars from '%s'", len(questions), len(full_text), path.name)
                    return full_text, questions, meta
            except Exception as m_err:
                logger.warning("Vision model %s failed on '%s': %s", m_name, path.name, m_err)
                continue

    except Exception as exc:
        logger.exception("Visual question extraction failed for '%s': %s", path.name, exc)

    return "", [], {"success": False, "method": "vision_error", "confidence": 0.0}


def extract_text_hybrid(image_or_path: Any, lang: Optional[str] = None) -> Tuple[str, float, bool]:
    """
    Hybrid text extraction: attempts Tesseract if available, else Gemini Vision.
    Returns: (text, confidence, success)
    """
    from PIL import Image
    if isinstance(image_or_path, (str, Path)):
        p = Path(image_or_path)
        if not p.exists():
            return "", 0.0, False
        try:
            with Image.open(str(p)) as img:
                return extract_text_hybrid(img, lang=lang)
        except Exception:
            return "", 0.0, False

    # Try Tesseract if installed
    if is_tesseract_available():
        text, conf, success = extract_text_with_confidence(image_or_path, lang=lang)
        if success and conf >= 60.0 and len(text) > 30:
            return text, conf, True

    # Fallback to Gemini Vision
    try:
        gemini_key = _get_gemini_api_key()
        if gemini_key:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-3.6-flash")
            pil_img = preprocess_image_for_vision(image_or_path)
            res = model.generate_content([
                "Transcribe all readable text from this document image with high fidelity. "
                "Preserve question numbering, tables, sections, and format math equations in LaTeX.",
                pil_img
            ])
            text = res.text.strip()
            if text:
                return text, 95.0, True
    except Exception as exc:
        logger.warning("Hybrid vision fallback error: %s", exc)

    return "", 0.0, False


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
    Perform high-precision structured question paper and image extraction.
    
    Pipeline:
      1. Sidecar cache validation (*_ocr.txt, *_questions.json)
      2. Multimodal Gemini Vision question extraction (questions, options, LaTeX math, diagrams)
      3. Fallback to adaptive Tesseract OCR if vision unavailable
      4. Generates structure-preserving TextChunks with question_number, section, and marks
    
    Returns:
      (extracted_text: str, chunks: List[TextChunk], metadata: Dict[str, Any])
    """
    from services.pdf_service import _split_into_structured_chunks, TextChunk

    img_path = Path(image_path)
    sidecar_path = img_path.parent / f"{img_path.stem}_ocr.txt"
    meta_path = img_path.parent / f"{img_path.stem}_ocr.json"
    questions_path = img_path.parent / f"{img_path.stem}_questions.json"

    extracted_text = ""
    questions: List[Dict[str, Any]] = []
    ocr_conf = 0.0
    ocr_success = False
    extraction_method = "vision"

    # 1. Check existing sidecar cache
    if sidecar_path.exists():
        cached_text = sidecar_path.read_text(encoding="utf-8", errors="ignore").strip()
        if cached_text and not cached_text.startswith("[Image Document:"):
            extracted_text = cached_text
            ocr_success = True
            if meta_path.exists():
                try:
                    meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
                    ocr_conf = float(meta_data.get("confidence", 95.0))
                    extraction_method = meta_data.get("method", "vision")
                except Exception:
                    ocr_conf = 95.0

            if questions_path.exists():
                try:
                    q_data = json.loads(questions_path.read_text(encoding="utf-8"))
                    questions = q_data.get("questions", [])
                except Exception:
                    questions = []
            logger.debug("Loaded structured OCR/Vision text from sidecar cache for '%s'", img_path.name)

    # 2. Extract fresh content if not cached
    if not extracted_text:
        # A. Primary: Gemini Vision Structured Question Extraction
        try:
            full_text, q_list, v_meta = extract_structured_question_paper(str(img_path))
            if v_meta.get("success") and full_text.strip():
                extracted_text = full_text.strip()
                questions = q_list
                ocr_conf = v_meta.get("confidence", 96.0)
                ocr_success = True
                extraction_method = "vision"

                # Write persistent sidecars
                try:
                    sidecar_path.write_text(extracted_text, encoding="utf-8")
                    questions_path.write_text(
                        json.dumps({
                            "title": v_meta.get("title", ""),
                            "sections": v_meta.get("sections", []),
                            "questions": questions,
                        }, indent=2),
                        encoding="utf-8",
                    )
                    meta_path.write_text(
                        json.dumps({
                            "filename": img_path.name,
                            "confidence": ocr_conf,
                            "success": True,
                            "method": "vision",
                            "char_count": len(extracted_text),
                            "question_count": len(questions),
                        }),
                        encoding="utf-8",
                    )
                except Exception as sidecar_err:
                    logger.warning("Failed to write sidecars for '%s': %s", img_path.name, sidecar_err)

        except Exception as vision_err:
            logger.warning("Vision question extraction error for '%s': %s", img_path.name, vision_err)

        # B. Fallback to Tesseract OCR if Vision was unavailable
        if not extracted_text:
            try:
                from PIL import Image
                with Image.open(str(img_path)) as img:
                    extracted_text, ocr_conf, ocr_success = extract_text_with_confidence(img, lang=lang)
                    if ocr_success:
                        extraction_method = "ocr"
                        try:
                            sidecar_path.write_text(extracted_text, encoding="utf-8")
                            meta_path.write_text(
                                json.dumps({
                                    "filename": img_path.name,
                                    "confidence": ocr_conf,
                                    "success": True,
                                    "method": "ocr",
                                    "char_count": len(extracted_text),
                                    "question_count": 0,
                                }),
                                encoding="utf-8",
                            )
                        except Exception:
                            pass
            except Exception as ocr_err:
                logger.warning("Tesseract OCR fallback failed for '%s': %s", img_path.name, ocr_err)

    # 3. Build structured text chunks
    chunks: List[TextChunk] = []
    if questions and ocr_success:
        # Build individual structured question chunks
        for idx, q in enumerate(questions):
            q_num = q.get("q_num", f"Q{idx + 1}")
            sec = q.get("section", "")
            marks = q.get("marks", "")
            q_body = q.get("text", "")
            options = q.get("options", [])
            opt_str = ("\nOptions: " + " | ".join(options)) if options else ""
            diag_str = f"\n[Diagram/Figure: {q['diagram_description']}]" if q.get("has_diagram") and q.get("diagram_description") else ""
            sec_header = f"[{sec}] " if sec else ""
            marks_suffix = f" ({marks})" if marks else ""
            chunk_body = f"{sec_header}{q_num}: {q_body}{opt_str}{diag_str}{marks_suffix}".strip()

            chunks.append(
                TextChunk(
                    text=chunk_body,
                    page=1,
                    chunk_index=idx,
                    doc_id=doc_id,
                    is_ocr=True,
                    source=img_path.name,
                    question_number=q_num,
                    section=sec,
                    marks=marks,
                )
            )

        # Also add an introductory overview chunk if full text has headers/instructions
        if len(extracted_text) > 200:
            chunks.insert(
                0,
                TextChunk(
                    text=extracted_text[:600],
                    page=1,
                    chunk_index=len(chunks),
                    doc_id=doc_id,
                    is_ocr=True,
                    source=img_path.name,
                    question_number="Overview",
                    section="",
                    marks="",
                )
            )

    elif extracted_text and ocr_success:
        # Fallback to paragraph/sentence chunker
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
        "extraction_method": extraction_method,
        "ocr_success": ocr_success,
        "ocr_confidence": ocr_conf,
        "char_count": len(extracted_text),
        "chunk_count": len(chunks),
        "question_count": len(questions),
        "questions": questions,
        "filename": img_path.name,
    }

    return extracted_text, chunks, metadata
