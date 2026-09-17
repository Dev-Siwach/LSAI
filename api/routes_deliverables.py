"""Deliverables API Routes for Secure Artifact Retrieval.

Provides secure downloading and listing of generated industrial deliverables
(.docx approval notes, .xlsx calculation workbooks, .pptx slides, .py verified scripts)
with strict path traversal enforcement.
"""

from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Deliverables"])

# MIME type mapping for industrial artifacts
MIME_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".pdf": "application/pdf",
    ".py": "text/x-python",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
}


def _validate_deliverable_path(filename: str) -> Path:
    """Validate filename against path traversal and return resolved path inside deliverables dir."""
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="Filename cannot be empty")

    # Reject traversal patterns in raw string
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid characters or traversal sequence in filename")

    settings = get_settings()
    deliverables_dir = settings.DELIVERABLES_DIR.resolve()
    target_path = (deliverables_dir / filename).resolve()

    try:
        if not target_path.is_relative_to(deliverables_dir):
            raise HTTPException(status_code=403, detail="Access denied: Path traversal detected")
    except AttributeError:
        if not str(target_path).startswith(str(deliverables_dir) + os.sep):
            raise HTTPException(status_code=403, detail="Access denied: Path traversal detected")

    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"Deliverable '{filename}' not found")

    return target_path


@router.get("/download/{filename}")
async def download_deliverable(filename: str):
    """Securely download a generated deliverable file (.docx, .xlsx, .pptx, .py)."""
    target_path = _validate_deliverable_path(filename)
    ext = target_path.suffix.lower()
    media_type = MIME_TYPES.get(ext) or mimetypes.guess_type(target_path.name)[0] or "application/octet-stream"

    return FileResponse(
        path=str(target_path),
        filename=target_path.name,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{target_path.name}"',
        },
    )


@router.get("/list")
async def list_deliverables() -> List[Dict[str, Any]]:
    """List all verified deliverable files currently available in workspace."""
    settings = get_settings()
    settings.DELIVERABLES_DIR.mkdir(parents=True, exist_ok=True)

    files = []
    for p in sorted(settings.DELIVERABLES_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file():
            stat = p.stat()
            ext = p.suffix.lower()
            files.append({
                "filename": p.name,
                "size_bytes": stat.st_size,
                "extension": ext,
                "media_type": MIME_TYPES.get(ext, "application/octet-stream"),
                "modified_time": stat.st_mtime,
                "download_url": f"/api/deliverables/download/{p.name}",
            })
    return files


@router.get("/info/{filename}")
async def get_deliverable_info(filename: str) -> Dict[str, Any]:
    """Inspect metadata for a specific deliverable file."""
    target_path = _validate_deliverable_path(filename)
    stat = target_path.stat()
    ext = target_path.suffix.lower()

    return {
        "filename": target_path.name,
        "filepath": str(target_path),
        "size_bytes": stat.st_size,
        "extension": ext,
        "media_type": MIME_TYPES.get(ext, "application/octet-stream"),
        "created_time": stat.st_ctime,
        "modified_time": stat.st_mtime,
        "download_url": f"/api/deliverables/download/{target_path.name}",
    }


@router.delete("/{filename}", status_code=status.HTTP_200_OK)
async def delete_deliverable(filename: str) -> Dict[str, Any]:
    """Delete a deliverable file from the workspace."""
    target_path = _validate_deliverable_path(filename)
    target_path.unlink()
    return {"filename": filename, "deleted": True}
