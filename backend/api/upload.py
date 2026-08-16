"""
api/upload.py
Document upload, extraction, and vector indexing endpoint for SS SPARK.
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
from database.models import UploadedDoc, save_document
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
    Upload one or multiple documents, extract text, generate embeddings,
    and index them in both Vector Store (Qdrant/ChromaDB) and PaperQA RAG.
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

    uploaded_results = []
    user_id = current_user.id if current_user else None

    for file in files:
        filename = Path(file.filename).name
        suffix = Path(filename).suffix.lower()

        # Check allowed extensions
        if suffix not in settings.ALLOWED_EXTENSIONS:
            logger.warning("Unsupported file extension rejected: %s", suffix)
            continue

        doc_id = str(uuid.uuid4())
        safe_filename = f"{doc_id[:8]}_{filename}"
        dest_path = upload_dir / safe_filename

        # Write uploaded file to disk
        try:
            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as exc:
            logger.error("Failed to save uploaded file: %s", exc)
            continue

        file_size_mb = round(dest_path.stat().st_size / (1024 * 1024), 2)
        pages_count = 1
        chunks = []

        # Extract text based on file type (offloaded to thread to keep async event loop responsive)
        if suffix in (".png", ".jpg", ".jpeg", ".webp"):
            kind = "image"
            _, chunks = await asyncio.to_thread(
                process_image_to_chunks,
                str(dest_path),
                doc_id=doc_id,
                upload_dir=str(upload_dir),
                chunk_size=settings.CHUNK_SIZE,
                overlap=settings.CHUNK_OVERLAP,
            )
        else:
            kind = "docx" if suffix in (".docx", ".doc") else ("txt" if suffix == ".txt" else "pdf")
            pages_count = await asyncio.to_thread(count_pdf_pages, str(dest_path))
            chunks = await asyncio.to_thread(
                extract_chunks,
                str(dest_path),
                doc_id=doc_id,
                chunk_size=settings.CHUNK_SIZE,
                overlap=settings.CHUNK_OVERLAP,
            )

        # Index vectors into vector store
        chunks_indexed = 0
        if chunks:
            try:
                texts = [c.text for c in chunks]
                page_nums = [c.page for c in chunks]
                embeddings = await asyncio.to_thread(embedder.embed, texts)
                vs.add_chunks(
                    doc_id=doc_id,
                    source_name=filename,
                    chunks=texts,
                    embeddings=embeddings,
                    pages=page_nums,
                    user_id=user_id,
                )
                chunks_indexed = len(chunks)
            except Exception as exc:
                logger.warning("Vector store indexing failed for %s: %s", filename, exc)

        # Index into PaperQA connector with user isolation
        pqa_indexed = False
        try:
            pqa_indexed = await pqa.add_document(str(dest_path), user_id=user_id)
        except Exception as exc:
            logger.warning("PaperQA indexing failed for %s: %s", filename, exc)

        # Save to database
        doc_record = UploadedDoc(
            id=doc_id,
            name=filename,
            kind=kind,
            size_mb=file_size_mb,
            pages=pages_count,
            chunk_count=chunks_indexed,
            file_path=str(dest_path),
            user_id=current_user.id if current_user else None,
        )
        await save_document(doc_record)
        if current_user:
            await record_audit_log(
                current_user.id,
                LogAction.UPLOAD,
                f"Uploaded document: {filename} ({file_size_mb} MB, {pages_count} pages)",
            )

        uploaded_results.append({
            "id": doc_id,
            "filename": filename,
            "kind": kind,
            "size_mb": file_size_mb,
            "pages": pages_count,
            "chunks_indexed": chunks_indexed,
            "paperqa_indexed": pqa_indexed,
            "uploaded_at": doc_record.uploaded_at,
            "message": "Processed and indexed successfully.",
        })

    return {
        "success": True,
        "data": uploaded_results,
        "message": f"Successfully processed and indexed {len(uploaded_results)} document(s).",
    }
