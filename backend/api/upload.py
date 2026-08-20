"""
api/upload.py
Document and Question Paper upload, hybrid OCR extraction, and dual vector indexing endpoint for SS SPARK.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from core.config import Settings, get_settings
from core.security import get_optional_user
import hashlib
from database.models import UploadedDoc, get_document_by_hash, save_document

def _calc_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()
from database.user_models import LogAction, UserRecord, record_audit_log
from rag import paperqa_connector as pqa
from rag.embeddings import get_embedder
from rag.vector_store import get_vector_store
from services.image_service import process_image_to_chunks
from services.pdf_service import count_pdf_pages, extract_chunks

logger = logging.getLogger("ss_spark.upload_api")
router = APIRouter(prefix="/api/upload", tags=["Upload"])


@router.post("")
async def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: Optional[UserRecord] = Depends(get_optional_user),
    settings: Settings = Depends(get_settings),
):
    """
    Upload one or multiple documents, extract text via hybrid digital/OCR pipelines,
    generate vector embeddings, and index into Vector Store (Qdrant/ChromaDB) and PaperQA RAG.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded.",
        )

    upload_dir = settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    vs = get_vector_store()
    embedder = get_embedder()
    user_id = current_user.id if current_user else None

    # Semaphore to prevent unbounded memory spikes during concurrent OCR operations
    sem = asyncio.Semaphore(4)

    def _save_file_to_disk(dest: Path, file_obj) -> None:
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer)

    async def _process_file(file: UploadFile) -> Optional[dict]:
        async with sem:
            filename = Path(file.filename).name
            suffix = Path(filename).suffix.lower()

            # Check allowed extensions
            if suffix not in settings.ALLOWED_EXTENSIONS:
                logger.warning("Unsupported file extension rejected: %s", suffix)
                return None

            doc_id = str(uuid.uuid4())
            safe_filename = f"{doc_id[:8]}_{filename}"
            dest_path = upload_dir / safe_filename

            # Non-blocking write to disk
            try:
                await asyncio.to_thread(_save_file_to_disk, dest_path, file.file)
            except Exception as exc:
                logger.error("Failed to save uploaded file '%s': %s", filename, exc)
                return None

            file_size_mb = round(dest_path.stat().st_size / (1024 * 1024), 2)
            
            # UPL-01: Calculate SHA-256 and check for user-scoped duplicate
            file_hash = await asyncio.to_thread(_calc_sha256, dest_path)
            existing_doc = await get_document_by_hash(user_id=user_id, sha256_hash=file_hash)
            if existing_doc:
                logger.info("Duplicate document detected for user %s (sha256=%s). Reusing ID %s.", user_id, file_hash[:8], existing_doc.id)
                dest_path.unlink(missing_ok=True)
                return {
                    "id": existing_doc.id,
                    "name": existing_doc.name,
                    "filename": existing_doc.name,
                    "kind": existing_doc.kind,
                    "size_mb": existing_doc.size_mb,
                    "pages": existing_doc.pages,
                    "chunk_count": existing_doc.chunk_count,
                    "chunks_indexed": existing_doc.chunk_count,
                    "paperqa_indexed": True,
                    "extraction_method": "digital",
                    "ocr_success": True,
                    "ocr_confidence": 100.0,
                    "uploaded_at": existing_doc.uploaded_at,
                    "message": "Document already indexed.",
                }
            pages_count = 1
            chunks = []
            extracted_text = ""
            extraction_method = "digital"
            ocr_success = True
            ocr_conf = 0.0

            # 1. Extraction Pipeline Dispatch
            if suffix in (".png", ".jpg", ".jpeg", ".webp"):
                kind = "image"
                extraction_method = "ocr"
                extracted_text, chunks, ocr_meta = await asyncio.to_thread(
                    process_image_to_chunks,
                    str(dest_path),
                    doc_id=doc_id,
                    upload_dir=str(upload_dir),
                    chunk_size=settings.CHUNK_SIZE,
                    overlap=settings.CHUNK_OVERLAP,
                    lang=settings.OCR_LANG,
                )
                ocr_success = ocr_meta.get("ocr_success", bool(chunks))
                ocr_conf = ocr_meta.get("ocr_confidence", 0.0)
                pages_count = 1

            else:
                kind = "docx" if suffix in (".docx", ".doc") else ("txt" if suffix == ".txt" else "pdf")
                pages_task = asyncio.to_thread(count_pdf_pages, str(dest_path))
                chunks_task = asyncio.to_thread(
                    extract_chunks,
                    str(dest_path),
                    doc_id=doc_id,
                    chunk_size=settings.CHUNK_SIZE,
                    overlap=settings.CHUNK_OVERLAP,
                    lang=settings.OCR_LANG,
                )
                pages_count, chunks = await asyncio.gather(pages_task, chunks_task)

                has_ocr_chunks = any(getattr(c, "is_ocr", False) for c in chunks)
                extraction_method = "hybrid" if has_ocr_chunks else "digital"

            # 2. Vector Store Indexing (Qdrant / ChromaDB)
            chunks_indexed = 0
            if chunks:
                try:
                    texts = [c.text for c in chunks]
                    page_nums = [c.page for c in chunks]
                    embeddings = await asyncio.to_thread(embedder.embed, texts)
                    await asyncio.to_thread(
                        vs.add_chunks,
                        doc_id=doc_id,
                        source_name=filename,
                        chunks=texts,
                        embeddings=embeddings,
                        pages=page_nums,
                        user_id=user_id,
                    )
                    chunks_indexed = len(chunks)
                    logger.info("Indexed %d chunks for '%s' into VectorStore (user_id=%s)", chunks_indexed, filename, user_id)
                except Exception as exc:
                    logger.warning("Vector store indexing failed for %s: %s", filename, exc)

            # 3. PaperQA Background Ingestion (RAG-01: Non-blocking background indexing)
            async def _bg_pqa_index():
                try:
                    if kind == "image" and extracted_text.strip():
                        await pqa.add_text_content(text=extracted_text, source_name=filename, user_id=user_id)
                    elif kind == "pdf" and any(getattr(c, "is_ocr", False) for c in chunks) and len(chunks) > 0:
                        full_doc_text = "\n\n".join(c.text for c in chunks)
                        await pqa.add_text_content(text=full_doc_text, source_name=filename, user_id=user_id)
                    else:
                        await pqa.add_document(str(dest_path), user_id=user_id)
                except Exception as exc:
                    logger.debug("Background PaperQA indexing: %s", exc)

            asyncio.create_task(_bg_pqa_index())
            pqa_indexed = True

            # 4. Save Record to Database
            doc_record = UploadedDoc(
                id=doc_id,
                name=filename,
                kind=kind,
                size_mb=file_size_mb,
                pages=pages_count,
                chunk_count=chunks_indexed,
                file_path=str(dest_path),
                user_id=user_id,
                sha256=file_hash,
            )
            await save_document(doc_record)

            if current_user:
                await record_audit_log(
                    current_user.id,
                    LogAction.UPLOAD,
                    f"Uploaded document: {filename} ({file_size_mb} MB, {pages_count} pages, {chunks_indexed} chunks, {extraction_method})",
                )

            # Warning if OCR failed to find readable text
            msg = "Processed and indexed successfully."
            if kind == "image" and not chunks:
                msg = "Warning: Text could not be reliably detected in this image. Please upload a clearer image."

            return {
                "id": doc_id,
                "name": filename,
                "filename": filename,
                "kind": kind,
                "size_mb": file_size_mb,
                "pages": pages_count,
                "chunk_count": chunks_indexed,
                "chunks_indexed": chunks_indexed,
                "paperqa_indexed": pqa_indexed,
                "extraction_method": extraction_method,
                "ocr_success": ocr_success if kind == "image" else True,
                "ocr_confidence": ocr_conf if kind == "image" else 100.0,
                "uploaded_at": doc_record.uploaded_at,
                "message": msg,
            }

    # Process all files concurrently
    tasks = [_process_file(f) for f in files]
    results = await asyncio.gather(*tasks)
    uploaded_results = [r for r in results if r is not None]

    # Invalidate cached document listings
    try:
        from services.chat_service import invalidate_doc_cache
        invalidate_doc_cache(user_id=user_id)
    except Exception:
        pass

    return {
        "success": True,
        "data": uploaded_results,
        "message": f"Successfully processed and indexed {len(uploaded_results)} document(s).",
    }
