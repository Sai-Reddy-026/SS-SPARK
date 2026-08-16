"""
api/documents.py
Document management endpoints for SS SPARK.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.security import get_optional_user
from database.models import delete_document, get_document_by_id, get_documents, rename_document
from database.user_models import UserRecord
from rag.vector_store import get_vector_store

logger = logging.getLogger("ss_spark.documents_api")
router = APIRouter(prefix="/api/documents", tags=["Documents"])


class RenameRequest(BaseModel):
    name: str


@router.get("")
async def list_documents(current_user: Optional[UserRecord] = Depends(get_optional_user)):
    """List all uploaded documents."""
    user_id = current_user.id if current_user else None
    docs = await get_documents(user_id=user_id)
    return {
        "success": True,
        "data": [
            {
                "id": d.id,
                "name": d.name,
                "kind": d.kind,
                "size_mb": d.size_mb,
                "pages": d.pages,
                "chunk_count": d.chunk_count,
                "uploaded_at": d.uploaded_at,
                "user_id": d.user_id,
            }
            for d in docs
        ],
    }


@router.delete("/{doc_id}")
async def delete_doc(
    doc_id: str,
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Delete an uploaded document, its vectors, and its file on disk."""
    user_id = current_user.id if current_user else None
    doc = await get_document_by_id(doc_id, user_id=user_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # 1. Delete vector store chunks
    vs = get_vector_store()
    vs.delete_by_doc_id(doc_id)

    # 2. Delete file from disk if it exists
    if doc.file_path and Path(doc.file_path).exists():
        try:
            Path(doc.file_path).unlink(missing_ok=True)
            # Remove OCR sidecar if present
            sidecar = Path(doc.file_path).parent / f"{Path(doc.file_path).stem}_ocr.txt"
            sidecar.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Could not delete file from disk: %s", exc)

    # 3. Delete database record
    await delete_document(doc_id, user_id=user_id)

    return {
        "success": True,
        "message": f"Document '{doc.name}' deleted successfully.",
    }


@router.patch("/{doc_id}")
async def rename_doc(
    doc_id: str,
    req: RenameRequest,
    current_user: Optional[UserRecord] = Depends(get_optional_user),
):
    """Rename a document."""
    user_id = current_user.id if current_user else None
    updated = await rename_document(doc_id, req.name, user_id=user_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    return {
        "success": True,
        "data": updated.model_dump(),
        "message": "Document renamed successfully.",
    }
