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
    assert settings.auth_cookie_secure is False
    assert settings.auth_cookie_samesite == "lax"


def test_production_requires_secure_auth_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db/zsme")
    monkeypatch.setenv("SECRET_KEY", "a-production-secret-key-with-at-least-32-characters")

    with pytest.raises(ValidationError, match="AUTH_COOKIE_SECURE"):
        Settings()


def test_production_rejects_non_postgresql_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "a-production-secret-key-with-at-least-32-characters")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")

    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings()


def test_malformed_json_cors_configuration_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "[broken-json")
    settings = Settings()

    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        _ = settings.cors_origin_list
