"""Fixtures for unit tests (mock-based, no real database)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from maia_vectordb.core.auth import verify_api_key
from maia_vectordb.db.engine import get_db_session
from maia_vectordb.main import app


@pytest.fixture()
def mock_session() -> MagicMock:
    """Return a mock async session with sync methods as plain MagicMock.

    ``session.add`` and ``session.add_all`` are synchronous in SQLAlchemy, so
    we use a ``MagicMock`` base with async overrides for truly-async methods
    (``commit``, ``refresh``, ``execute``, ``get``, ``delete``).
    """
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture()
def client(mock_session: MagicMock) -> Generator[TestClient, None, None]:
    """TestClient with the DB session dependency and auth overridden."""

    async def _override() -> Any:
        yield mock_session

    app.dependency_overrides[get_db_session] = _override
    app.dependency_overrides[verify_api_key] = lambda: "test-key"
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def fake_embedding() -> list[float]:
    """A 1536-dimensional fake embedding vector."""
    return [0.1] * 1536
