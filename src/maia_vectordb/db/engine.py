"""Async SQLAlchemy engine and session management."""

import logging
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from maia_vectordb.core.config import settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# Tables that must exist before the app can serve requests.
# UPDATE THIS SET when adding new ORM models via Alembic migrations.
_REQUIRED_TABLES = {"vector_stores", "files", "file_chunks"}


def _create_engine() -> AsyncEngine:
    """Create an async SQLAlchemy engine with connection pooling."""
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        pool_recycle=300,
    )


async def init_engine() -> None:
    """Initialise async engine, verify pgvector + schema, and create session factory.

    Tables are managed by Alembic migrations. This function verifies that
    they exist (fast) rather than running CREATE TABLE (slow on large tables
    due to HNSW index creation).
    """
    global _engine, _session_factory  # noqa: PLW0603

    _engine = _create_engine()

    async with _engine.begin() as conn:
        # Ensure pgvector extension is loaded (fast, idempotent)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Verify required tables exist — don't CREATE them (that's Alembic's job)
        result = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ))
        existing = {row[0] for row in result.fetchall()}
        missing = _REQUIRED_TABLES - existing

        if missing:
            logger.warning(
                "Required tables missing: %s — running Alembic migrations as fallback",
                missing,
            )
            # Fallback: create tables for fresh installs / dev environments
            import maia_vectordb.models  # noqa: F401
            from maia_vectordb.db.base import Base
            await conn.run_sync(Base.metadata.create_all)
        else:
            logger.info("Schema verified — all required tables present")

    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_engine() -> None:
    """Dispose of the async engine and release connections."""
    global _engine, _session_factory  # noqa: PLW0603

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory for background tasks."""
    if _session_factory is None:
        raise RuntimeError("Database engine not initialised. Call init_engine() first.")
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session (FastAPI dependency)."""
    if _session_factory is None:
        raise RuntimeError("Database engine not initialised. Call init_engine() first.")

    async with _session_factory() as session:
        yield session
