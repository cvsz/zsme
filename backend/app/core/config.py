import json
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+psycopg://zsme:zsme@localhost:5432/zsme"
DEFAULT_SECRET_KEY = "development-only-change-this-secret-key"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = Field(default="development", validation_alias="APP_ENV")
    database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        validation_alias="DATABASE_URL",
    )
    database_connect_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        validation_alias="DATABASE_CONNECT_TIMEOUT_SECONDS",
    )
    database_statement_timeout_ms: int = Field(
        default=30_000,
        ge=1_000,
        le=120_000,
        validation_alias="DATABASE_STATEMENT_TIMEOUT_MS",
    )
    secret_key: str = Field(
        default=DEFAULT_SECRET_KEY,
        validation_alias="SECRET_KEY",
    )
    access_token_ttl_minutes: int = Field(
        default=30,
        ge=5,
        le=24 * 60,
        validation_alias="ACCESS_TOKEN_TTL_MINUTES",
    )
    cors_origins: str = Field(default="", validation_alias="CORS_ORIGINS")
    request_body_limit_bytes: int = Field(
        default=1_048_576,
        ge=64 * 1024,
        le=20 * 1024 * 1024,
        validation_alias="REQUEST_BODY_LIMIT_BYTES",
    )
    login_max_failures: int = Field(
        default=5,
        ge=1,
        le=20,
        validation_alias="LOGIN_MAX_FAILURES",
    )
    login_window_seconds: int = Field(
        default=300,
        ge=30,
        le=3_600,
        validation_alias="LOGIN_WINDOW_SECONDS",
    )
    login_block_seconds: int = Field(
        default=900,
        ge=60,
        le=86_400,
        validation_alias="LOGIN_BLOCK_SECONDS",
    )

    @field_validator("environment", "database_url")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("configuration value must not be blank")
        return normalized

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return []
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
            return []
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if self.environment.lower() in {"production", "prod"}:
            if self.secret_key == DEFAULT_SECRET_KEY or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters and explicitly "
                    "configured in production"
                )
            if not self.database_url or self.database_url == DEFAULT_DATABASE_URL:
                raise ValueError("DATABASE_URL must be explicitly configured in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
