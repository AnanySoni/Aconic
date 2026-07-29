import json
from typing import Any, Optional
from uuid import UUID

import redis

from app.core.config import get_settings

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def documents_cache_key(user_id: UUID) -> str:
    return f"docs:user:{user_id}"


def get_cached_documents(user_id: UUID) -> Optional[list[dict[str, Any]]]:
    try:
        raw = get_redis().get(documents_cache_key(user_id))
        if raw:
            return json.loads(raw)
    except Exception:
        return None
    return None


def set_cached_documents(user_id: UUID, payload: list[dict[str, Any]], ttl: int = 30) -> None:
    try:
        get_redis().setex(documents_cache_key(user_id), ttl, json.dumps(payload, default=str))
    except Exception:
        pass


def invalidate_documents_cache(user_id: UUID) -> None:
    try:
        get_redis().delete(documents_cache_key(user_id))
    except Exception:
        pass
