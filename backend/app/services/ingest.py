from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk, DocumentStatus
from app.db.session import SessionLocal
from app.services.llm import chunk_text, embed_texts
from app.services.parsers import extract_text


def ingest_document(document_id: str) -> str:
    db: Session = SessionLocal()
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            return "missing"

        # Avoid racing a successful inline ingest on another service.
        if doc.status == DocumentStatus.ready and doc.extracted_text:
            return "already_ready"

        doc.status = DocumentStatus.processing
        doc.error_message = None
        db.commit()

        text = extract_text(doc.storage_path)
        if not text or not text.strip():
            doc.status = DocumentStatus.failed
            doc.error_message = "No extractable text found in the uploaded file"
            db.commit()
            return "empty"

        chunks = chunk_text(text)
        if not chunks:
            doc.status = DocumentStatus.failed
            doc.error_message = "Document produced no usable text chunks"
            db.commit()
            return "empty"

        embeddings = embed_texts(chunks)

        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        for idx, (content, emb) in enumerate(zip(chunks, embeddings)):
            db.add(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    content=content,
                    embedding=emb,
                    token_count=len(content.split()),
                )
            )

        doc.extracted_text = text
        doc.status = DocumentStatus.ready
        doc.error_message = None
        db.commit()
        return "ready"
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        doc = db.get(Document, UUID(document_id))
        if doc is not None:
            doc.status = DocumentStatus.failed
            doc.error_message = str(exc)[:1000]
            db.commit()
        return f"failed:{exc}"
    finally:
        db.close()
