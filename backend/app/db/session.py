from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _register_vector(dbapi_connection, connection_record) -> None:  # noqa: ARG001
    try:
        from pgvector.psycopg2 import register_vector

        register_vector(dbapi_connection)
    except Exception:
        pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_pgvector_extension() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
