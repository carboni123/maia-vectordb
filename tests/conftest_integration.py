"""Fixtures for integration tests that hit a real PostgreSQL + pgvector database.

Usage:
    pytest tests/test_integration_db.py -v -m integration

Requires a PostgreSQL server at localhost:5432 with pgvector extension.
The test database ``maia_vectors_test`` is created/dropped automatically.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from maia_vectordb.db.base import Base
from maia_vectordb.services.embedding_provider import MockEmbeddingProvider

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PG_USER = "postgres"
_PG_PASSWORD = "postgres"
_PG_HOST = "localhost"
_PG_PORT = 5432
_TEST_DB = "maia_vectors_test"
_ADMIN_DSN = f"postgresql://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/postgres"
_TEST_DSN = (
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/{_TEST_DB}"
)

_mock_provider = MockEmbeddingProvider()


def _mock_embed_texts(texts: Any, *, model: Any = None) -> list[list[float]]:
    """Drop-in replacement for ``embed_texts`` that uses MockEmbeddingProvider."""
    return _mock_provider.embed_texts(texts)


# ---------------------------------------------------------------------------
# One-time DB bootstrap (runs before any async fixtures)
# ---------------------------------------------------------------------------


def _ensure_test_db_exists() -> None:
    """Create the test database and pgvector extension if they don't exist.

    Uses a standalone asyncio.run() that has no shared state with the engine.
    """

    async def _inner() -> None:
        conn = await asyncpg.connect(_ADMIN_DSN)
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname=$1", _TEST_DB
        )
        if not exists:
            await conn.execute(f"CREATE DATABASE {_TEST_DB}")
        await conn.close()

        conn = await asyncpg.connect(
            user=_PG_USER,
            password=_PG_PASSWORD,
            host=_PG_HOST,
            port=_PG_PORT,
            database=_TEST_DB,
        )
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.close()

    asyncio.run(_inner())


# Run once at import time — only creates DB, does NOT create an engine
_ensure_test_db_exists()


# ---------------------------------------------------------------------------
# Per-test fixtures (all share the pytest event loop)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """Create the SQLAlchemy engine and tables, then teardown after the test."""
    import maia_vectordb.models  # noqa: F401 — register models with Base

    engine = create_async_engine(_TEST_DSN, echo=False)

    # Create all tables fresh
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Teardown
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def session_factory(
    test_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Session factory bound to the test engine."""
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture()
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a clean DB session for direct database access in tests."""
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture()
async def integration_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """Async HTTP client wired to the real FastAPI app with test DB.

    - Overrides DB session dependency to use the test database.
    - Patches ``embed_texts`` to use MockEmbeddingProvider (no OpenAI calls).
    """
    from maia_vectordb.db.engine import get_db_session
    from maia_vectordb.main import app

    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db

    with (
        patch("maia_vectordb.api.files.embed_texts", side_effect=_mock_embed_texts),
        patch("maia_vectordb.api.search.embed_texts", side_effect=_mock_embed_texts),
    ):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def raw_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """A separate session for verifying DB state independently."""
    async with session_factory() as session:
        yield session
