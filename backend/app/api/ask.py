from __future__ import annotations

import json
from typing import AsyncGenerator, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import ChatHistory, Document, DocumentStatus, User
from app.db.session import get_db
from app.schemas import AskRequest, AskResponse, HistoryItem, HistoryResponse
from app.services.llm import stream_answer
from app.services.rag import answer_question, retrieve_chunks

router = APIRouter(tags=["ask"])


def _validate_document_ids(db: Session, user_id: UUID, document_ids: Optional[List[UUID]]) -> None:
    if not document_ids:
        return
    docs = db.scalars(
        select(Document).where(Document.id.in_(document_ids), Document.user_id == user_id)
    ).all()
    if len(docs) != len(set(document_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more documents not found")
    not_ready = [d.filename for d in docs if d.status != DocumentStatus.ready]
    if not_ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Documents not ready for Q&A: {', '.join(not_ready)}",
        )


@router.post("/ask")
async def ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_document_ids(db, current_user.id, payload.document_ids)

    if payload.stream:
        return StreamingResponse(
            _sse_stream(db, current_user, payload),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        answer, source_ids, _ = await answer_question(
            db, current_user.id, payload.question, payload.document_ids
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider error: {exc}",
        ) from exc

    history = ChatHistory(
        user_id=current_user.id,
        session_id=payload.session_id,
        document_ids=[str(i) for i in (payload.document_ids or source_ids)],
        question=payload.question,
        answer=answer,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    return AskResponse(answer=answer, sources=source_ids, history_id=history.id)


async def _sse_stream(
    db: Session, current_user: User, payload: AskRequest
) -> AsyncGenerator[str, None]:
    try:
        contexts = retrieve_chunks(db, current_user.id, payload.question, payload.document_ids)
        source_ids = list({c["document_id"] for c in contexts})
        yield f"event: meta\ndata: {json.dumps({'sources': [str(s) for s in source_ids]})}\n\n"

        parts: list[str] = []
        async for token in stream_answer(payload.question, contexts):
            parts.append(token)
            yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

        answer = "".join(parts)
        history = ChatHistory(
            user_id=current_user.id,
            session_id=payload.session_id,
            document_ids=[str(i) for i in (payload.document_ids or source_ids)],
            question=payload.question,
            answer=answer,
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        yield f"event: done\ndata: {json.dumps({'history_id': str(history.id), 'answer': answer})}\n\n"
    except Exception as exc:  # noqa: BLE001
        yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"


@router.get("/history", response_model=HistoryResponse)
def history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HistoryResponse:
    total = db.scalar(
        select(func.count()).select_from(ChatHistory).where(ChatHistory.user_id == current_user.id)
    ) or 0
    rows = db.scalars(
        select(ChatHistory)
        .where(ChatHistory.user_id == current_user.id)
        .order_by(ChatHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    items: List[HistoryItem] = []
    for row in rows:
        doc_ids = []
        for raw in row.document_ids or []:
            try:
                doc_ids.append(UUID(str(raw)))
            except ValueError:
                continue
        items.append(
            HistoryItem(
                id=row.id,
                question=row.question,
                answer=row.answer,
                document_ids=doc_ids,
                session_id=row.session_id,
                created_at=row.created_at,
            )
        )
    return HistoryResponse(items=items, total=total)
