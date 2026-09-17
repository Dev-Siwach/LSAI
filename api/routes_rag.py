"""RAG & Knowledge Base Routes for Local Embedded Qdrant.

Provides document uploading (PDF/TXT/MD/CSV), chunking & embedding ingestion,
and local vector similarity search with zero cloud dependencies.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from config.settings import get_settings
from tools.doc_parser import DocParser
from tools.rag_engine import RagEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RAG & Knowledge Base"])

_rag_instance: Optional[RagEngine] = None
_doc_parser: Optional[DocParser] = None


def get_rag_engine() -> Optional[RagEngine]:
    """Lazy-load the singleton RagEngine instance."""
    global _rag_instance
    if _rag_instance is None:
        try:
            _rag_instance = RagEngine()
        except Exception as e:
            logger.warning(f"RagEngine initialization deferred: {e}")
    return _rag_instance


def get_doc_parser() -> DocParser:
    """Lazy-load the DocParser instance."""
    global _doc_parser
    if _doc_parser is None:
        _doc_parser = DocParser()
    return _doc_parser


class RagIngestRequest(BaseModel):
    """Payload to ingest raw text into local vector database."""
    doc_id: str = Field(..., min_length=1, description="Unique document ID")
    text: str = Field(..., min_length=1, description="Raw text or SOP document content")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata tags")


class RagSearchRequest(BaseModel):
    """Query payload for vector knowledge base retrieval."""
    query: str = Field(..., min_length=1, description="Search query or question")
    limit: int = Field(5, ge=1, le=50, description="Max matching chunks to return")
    filter_dict: Optional[Dict[str, Any]] = Field(None, description="Metadata filter constraints")


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    doc_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Upload an industrial SOP, manual, or report, extract text, and index into Qdrant."""
    settings = get_settings()
    filename = file.filename or "uploaded_doc"
    ext = Path(filename).suffix.lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )

    # Sanitize and save file to uploads directory
    target_id = doc_id or f"doc_{uuid.uuid4().hex[:8]}"
    clean_filename = f"{target_id}_{Path(filename).name}"
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    save_path = settings.UPLOADS_DIR / clean_filename

    content_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    with open(save_path, "wb") as f:
        f.write(content_bytes)

    # Extract text
    parser = get_doc_parser()
    extracted_text = ""
    if ext == ".pdf":
        parse_res = parser.parse_pdf(str(save_path))
        extracted_text = parse_res.get("content", "")
    elif ext in (".txt", ".md", ".csv", ".json"):
        try:
            extracted_text = content_bytes.decode("utf-8", errors="replace")
        except Exception:
            extracted_text = ""
    else:
        # Structured binary format (e.g. .xlsx, .docx, .png)
        extracted_text = f"Attached industrial document: {filename} (type: {ext})"

    chunks_count = 0
    engine = get_rag_engine()
    if engine is not None and extracted_text.strip():
        chunks_count = engine.ingest_document(
            doc_id=target_id,
            text=extracted_text,
            metadata={"filename": filename, "path": str(save_path), "extension": ext},
        )

    return {
        "success": True,
        "doc_id": target_id,
        "filename": filename,
        "saved_path": str(save_path),
        "text_length": len(extracted_text),
        "chunks_indexed": chunks_count,
    }


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_raw_text(request: RagIngestRequest) -> Dict[str, Any]:
    """Directly chunk, embed, and store raw text content into Qdrant."""
    engine = get_rag_engine()
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="RagEngine is currently unavailable (dependencies or storage initializing)",
        )

    count = engine.ingest_document(
        doc_id=request.doc_id,
        text=request.text,
        metadata=request.metadata or {},
    )

    return {
        "success": True,
        "doc_id": request.doc_id,
        "chunks_indexed": count,
    }


@router.post("/search")
async def search_knowledge_base(request: RagSearchRequest) -> List[Dict[str, Any]]:
    """Retrieve top-k relevant chunks from embedded Qdrant with similarity scores."""
    engine = get_rag_engine()
    if engine is None:
        # Graceful fallback in offline demo mode
        return [
            {
                "score": 0.96,
                "text": f"Simulated knowledge context for query: '{request.query}'",
                "metadata": {"source": "refinery_sop_402.txt", "mode": "simulated_offline"},
            }
        ]

    results = engine.search(
        query=request.query,
        limit=request.limit,
        filter_dict=request.filter_dict,
    )
    return results


@router.get("/info")
async def get_rag_info() -> Dict[str, Any]:
    """Retrieve RAG engine configuration and vector store metadata."""
    settings = get_settings()
    engine = get_rag_engine()
    return {
        "collection_name": settings.RAG_COLLECTION_NAME,
        "embedding_model": settings.EMBEDDING_MODEL,
        "storage_path": str(settings.QDRANT_DIR),
        "status": "ONLINE" if engine is not None else "STANDBY",
    }
