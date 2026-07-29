from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk, DocumentStatus
from app.services.llm import embed_query, generate_answer, stream_answer


def retrieve_chunks(
    db: Session,
    user_id: UUID,
    question: str,
    document_ids: Optional[List[UUID]] = None,
    top_k: Optional[int] = None,
) -> List[dict]:
    settings = get_settings()
    k = top_k or settings.rag_top_k
    query_embedding = embed_query(question)

    filters = [
        Document.user_id == user_id,
        Document.status == DocumentStatus.ready,
    ]
    if document_ids:
        filters.append(Document.id.in_(document_ids))

    owned = list(db.scalars(select(Document.id).where(*filters)).all())
    if not owned:
        return []

    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.content,
            Document.filename,
            distance.label("distance"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.document_id.in_(owned), DocumentChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(k)
    )
    rows = db.execute(stmt).all()

    return [
        {
            "chunk_id": row.id,
            "document_id": row.document_id,
            "content": row.content,
            "filename": row.filename,
            "distance": float(row.distance) if row.distance is not None else None,
        }
        for row in rows
    ]


async def answer_question(
    db: Session,
    user_id: UUID,
    question: str,
    document_ids: Optional[List[UUID]] = None,
) -> tuple[str, List[UUID], List[dict]]:
    contexts = retrieve_chunks(db, user_id, question, document_ids)
    answer = await generate_answer(question, contexts)
    source_ids = list({c["document_id"] for c in contexts})
    return answer, source_ids, contexts
