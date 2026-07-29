from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://aconic:aconic@localhost:5432/aconic"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-to-a-long-random-secret-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    gemini_api_key: str = ""
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"
    max_upload_bytes: int = 10 * 1024 * 1024
    upload_dir: str = "uploads"
    embedding_dimensions: int = 768
    chunk_size: int = 800
    chunk_overlap: int = 150
    rag_top_k: int = 5
    gemini_chat_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
