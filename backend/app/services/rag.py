from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk, DocumentStatus
from app.services.llm import (
    embed_query,
    generate_answer,
    is_overview_question,
    map_reduce_summarize,
    stream_answer,
)


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


def retrieve_full_document_contexts(
    db: Session,
    user_id: UUID,
    document_ids: Optional[List[UUID]] = None,
) -> List[dict]:
    """Load all chunks (or full extracted text) for overview/summary questions."""
    settings = get_settings()
    filters = [
        Document.user_id == user_id,
        Document.status == DocumentStatus.ready,
    ]
    if document_ids:
        filters.append(Document.id.in_(document_ids))

    docs = list(
        db.scalars(select(Document).where(*filters).order_by(Document.created_at.desc())).all()
    )
    if not docs:
        return []

    contexts: List[dict] = []
    for doc in docs:
        if doc.extracted_text and len(doc.extracted_text) <= settings.full_doc_char_limit:
            contexts.append(
                {
                    "chunk_id": None,
                    "document_id": doc.id,
                    "content": doc.extracted_text,
                    "filename": doc.filename,
                    "distance": 0.0,
                }
            )
            continue

        chunks = db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).all()
        for chunk in chunks:
            contexts.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": doc.id,
                    "content": chunk.content,
                    "filename": doc.filename,
                    "distance": None,
                }
            )
    return contexts


def build_contexts_for_question(
    db: Session,
    user_id: UUID,
    question: str,
    document_ids: Optional[List[UUID]] = None,
) -> tuple[List[dict], bool]:
    overview = is_overview_question(question)
    if overview:
        contexts = retrieve_full_document_contexts(db, user_id, document_ids)
        return contexts, True
    return retrieve_chunks(db, user_id, question, document_ids), False


async def answer_question(
    db: Session,
    user_id: UUID,
    question: str,
    document_ids: Optional[List[UUID]] = None,
) -> tuple[str, List[UUID], List[dict]]:
    contexts, overview = build_contexts_for_question(db, user_id, question, document_ids)
    if overview and len(contexts) > 6 and all(c.get("chunk_id") is not None for c in contexts):
        # Many ordered chunks without a single full-text blob → map-reduce
        answer = await map_reduce_summarize(question, contexts)
    else:
        answer = await generate_answer(question, contexts, overview=overview)
    source_ids = list({c["document_id"] for c in contexts})
    return answer, source_ids, contexts


async def stream_question(
    db: Session,
    user_id: UUID,
    question: str,
    document_ids: Optional[List[UUID]] = None,
):
    contexts, overview = build_contexts_for_question(db, user_id, question, document_ids)
    source_ids = list({c["document_id"] for c in contexts})
    async for token in stream_answer(question, contexts, overview=overview):
        yield token, source_ids, contexts
