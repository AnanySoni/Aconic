from pathlib import Path
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import Document, DocumentStatus, User
from app.db.session import get_db
from app.schemas import DocumentOut
from app.services.cache import get_cached_documents, invalidate_documents_cache, set_cached_documents
from app.services.storage import save_upload
from app.workers.settings import enqueue_ingest

router = APIRouter(tags=["documents"])


def _serialize(doc: Document) -> dict:
    return {
        "id": doc.id,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "file_size": doc.file_size,
        "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        "error_message": doc.error_message,
        "created_at": doc.created_at,
    }


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    path, size, content_type = await save_upload(file, str(current_user.id))
    doc = Document(
        user_id=current_user.id,
        filename=file.filename or Path(path).name,
        content_type=content_type,
        file_size=size,
        storage_path=path,
        status=DocumentStatus.pending,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    invalidate_documents_cache(current_user.id)

    # Inline ingest keeps file + parsing on the same host (required when api/worker
    # do not share a volume). Optional ARQ enqueue for local Compose multi-service.
    from app.core.config import get_settings
    from app.services.ingest import ingest_document

    settings = get_settings()
    if getattr(settings, "enable_arq_ingest", False):
        try:
            await enqueue_ingest(str(doc.id))
        except Exception:
            ingest_document(str(doc.id))
            db.refresh(doc)
    else:
        ingest_document(str(doc.id))
        db.refresh(doc)

    return doc


@router.get("/documents", response_model=List[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Document]:
    cached = get_cached_documents(current_user.id)
    if cached is not None:
        return cached  # type: ignore[return-value]

    docs = db.scalars(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    ).all()
    payload = [_serialize(d) for d in docs]
    set_cached_documents(current_user.id, payload)
    return docs


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return doc


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    path = Path(doc.storage_path)
    db.delete(doc)
    db.commit()
    invalidate_documents_cache(current_user.id)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
