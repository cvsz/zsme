from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = Field(default="development", validation_alias="APP_ENV")
    database_url: str = Field(
        default="postgresql+psycopg://zsme:zsme@localhost:5432/zsme",
        validation_alias="DATABASE_URL",
    )
    secret_key: str = Field(
        default="development-only-change-this-secret-key",
        validation_alias="SECRET_KEY",
    )
    access_token_ttl_minutes: int = Field(
        default=30,
        ge=5,
        le=24 * 60,
        validation_alias="ACCESS_TOKEN_TTL_MINUTES",
    )

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if self.environment.lower() in {"production", "prod"} and len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
