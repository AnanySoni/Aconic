from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/octet-stream",
}


def ensure_upload_dir() -> Path:
    settings = get_settings()
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_upload(file: UploadFile, size: int) -> str:
    settings = get_settings()
    if size > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_bytes} bytes",
        )

    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, TXT",
        )

    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES and not content_type.startswith("text/"):
        # Still allow by extension if browsers send odd MIME types
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported content type '{content_type}'",
            )
    return ext


async def save_upload(file: UploadFile, user_id: str) -> tuple[str, int, str]:
    raw = await file.read()
    size = len(raw)
    ext = validate_upload(file, size)
    upload_dir = ensure_upload_dir() / user_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{ext}"
    path = upload_dir / stored_name
    path.write_bytes(raw)
    content_type = file.content_type or {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
    }.get(ext, "application/octet-stream")
    return str(path), size, content_type
