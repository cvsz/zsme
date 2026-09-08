from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


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
