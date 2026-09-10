from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def get_engine(database_url: str | None = None) -> Engine:
    if database_url is not None:
        return _create_engine(database_url)
    return _get_default_engine(get_settings().database_url)


def _create_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine_options: dict[str, object] = {}
    if url.startswith("postgresql"):
        settings = get_settings()
        connect_args = {
            "application_name": "zsme-api",
            "connect_timeout": settings.database_connect_timeout_seconds,
            "options": f"-c statement_timeout={settings.database_statement_timeout_ms}",
        }
        engine_options["pool_timeout"] = settings.database_connect_timeout_seconds
    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=1_800 if not url.startswith("sqlite") else -1,
        **engine_options,
    )


@lru_cache(maxsize=4)
def _get_default_engine(database_url: str) -> Engine:
    """Reuse the application engine instead of creating a pool per request."""
    return _create_engine(database_url)


def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    selected_engine = engine or get_engine()
    factory = sessionmaker(bind=selected_engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def managed_session(engine: Engine | None = None) -> Iterator[Session]:
    """Provide a transaction-scoped session for scripts and application services."""
    yield from session_scope(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that owns the request transaction lifecycle."""
    with managed_session() as session:
        yield session
