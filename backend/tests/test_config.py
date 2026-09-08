import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "a-secret-key-with-at-least-32-characters")

    settings = Settings()

    assert settings.database_url.startswith("sqlite")


def test_production_settings_reject_short_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "short")

    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings()


def test_settings_have_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("APP_ENV", "DATABASE_URL", "SECRET_KEY", "ACCESS_TOKEN_TTL_MINUTES"):
        monkeypatch.delenv(key, raising=False)

    settings = Settings()

    assert settings.environment == "development"
    assert settings.access_token_ttl_minutes == 30

