from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.services.ingest import ingest_document


async def ingest_document_job(ctx, document_id: str) -> str:  # noqa: ARG001
    return ingest_document(document_id)


class WorkerSettings:
    functions = [ingest_document_job]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 2
    job_timeout = 600


async def enqueue_ingest(document_id: str) -> None:
    settings = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await redis.enqueue_job("ingest_document_job", document_id)
    finally:
        await redis.close()
