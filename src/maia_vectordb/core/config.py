"""Application settings loaded from environment variables."""

from __future__ import annotations

from typing import Any, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # extra="ignore" lets .env carry keys for other providers
        extra="ignore",
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/maia_vectors"
    )
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 800
    chunk_overlap: int = 200
    api_keys: list[str] = []

    # Logging
    log_level: str = "INFO"

    # CORS — empty list means no origins are allowed (secure default)
    cors_origins: list[str] = []

    # Database connection pool
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Upload limit — default 10 MB
    max_file_size_bytes: int = 10 * 1024 * 1024

    # Rate limiting — max requests per minute per IP (0 = disabled)
    rate_limit_per_minute: int = 60

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, v: Any) -> list[str]:
        """Accept either a comma-separated string or a list."""
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return list(v)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Accept either a comma-separated string or a list."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return list(v)

    @model_validator(mode="after")
    def reject_empty_openai_key(self) -> Self:
        """Refuse to instantiate without an OpenAI API key."""
        if not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required. "
                "Set it via the OPENAI_API_KEY environment variable."
            )
        return self


settings = Settings()
