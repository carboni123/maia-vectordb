"""Application settings loaded from environment variables."""

from __future__ import annotations

from typing import Any

from pydantic import field_validator
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

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, v: Any) -> list[str]:
        """Accept either a comma-separated string or a list."""
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return list(v)


settings = Settings()
