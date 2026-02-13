"""Async SQLAlchemy engine and session management."""

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from maia_vectordb.core.config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _create_engine() -> AsyncEngine:
    """Create an async SQLAlchemy engine from settings."""
    return create_async_engine(settings.database_url, echo=False)


async def init_engine() -> None:
    """Initialise the async engine, register pgvector, and create session factory."""
    global _engine, _session_factory  # noqa: PLW0603

    _engine = _create_engine()

    # Register pgvector extension
    async with _engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_engine() -> None:
    """Dispose of the async engine and release connections."""
    global _engine, _session_factory  # noqa: PLW0603

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session (FastAPI dependency)."""
    if _session_factory is None:
        raise RuntimeError("Database engine not initialised. Call init_engine() first.")

    async with _session_factory() as session:
        yield session
