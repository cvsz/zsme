from sqlalchemy import Engine

from app.db.session import get_engine


def test_engine_is_lazy_and_uses_requested_url() -> None:
    engine = get_engine("sqlite+pysqlite:///:memory:")

    assert isinstance(engine, Engine)
    assert str(engine.url) == "sqlite+pysqlite:///:memory:"

