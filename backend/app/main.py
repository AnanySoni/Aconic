from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ask, auth, documents
from app.core.config import get_settings
from app.db.session import ensure_pgvector_extension
from app.services.storage import ensure_upload_dir


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_upload_dir()
    try:
        ensure_pgvector_extension()
    except Exception:
        # Extension may be created by Alembic migration instead
        pass
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Aconic Knowledge Base API",
        description="Upload documents and ask AI questions with RAG over your content.",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth.router)
    application.include_router(documents.router)
    application.include_router(ask.router)

    @application.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    return application


app = create_app()
