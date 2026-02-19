"""Shared test fixtures for the MAIA VectorDB test suite."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Set OPENAI_API_KEY before any maia_vectordb import so that Settings()
# (which now validates the key via model_validator) does not raise.
# The actual OpenAI client is never called in unit tests because embed_texts
# is always patched.
# ---------------------------------------------------------------------------
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from maia_vectordb.core.auth import verify_api_key  # noqa: E402
from maia_vectordb.core.config import settings  # noqa: E402
from maia_vectordb.db.engine import get_db_session  # noqa: E402
from maia_vectordb.main import app  # noqa: E402
from maia_vectordb.models.file import FileStatus  # noqa: E402
from maia_vectordb.models.vector_store import VectorStoreStatus  # noqa: E402

# ---------------------------------------------------------------------------
# Ensure api_keys is non-empty for all tests so:
#   1. Startup validation in lifespan() passes.
#   2. The verify_api_key dependency (when not overridden) can be satisfied
#      by sending headers={"X-API-Key": "test-key"}.
# ---------------------------------------------------------------------------
settings.api_keys = ["test-key"]

# ---------------------------------------------------------------------------
# Mock factory helpers
# ---------------------------------------------------------------------------

_STORE_ATTRS = (
    "id",
    "name",
    "metadata_",
    "file_counts",
    "status",
    "created_at",
    "updated_at",
    "expires_at",
)

_FILE_ATTRS = (
    "id",
    "vector_store_id",
    "filename",
    "status",
    "bytes",
    "purpose",
    "created_at",
)


def make_store(
    *,
    name: str = "test-store",
    metadata_: dict[str, Any] | None = None,
    store_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock that looks like a VectorStore ORM instance."""
    store = MagicMock()
    store.id = store_id or uuid.uuid4()
    store.name = name
    store.metadata_ = metadata_
    store.file_counts = None
    store.status = VectorStoreStatus.completed
    store.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    store.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
    store.expires_at = None
    return store


def make_file(
    *,
    vector_store_id: uuid.UUID,
    filename: str = "test.txt",
    status: FileStatus = FileStatus.in_progress,
    byte_size: int = 100,
    file_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock File ORM instance."""
    f = MagicMock()
    f.id = file_id or uuid.uuid4()
    f.vector_store_id = vector_store_id
    f.filename = filename
    f.status = status
    f.bytes = byte_size
    f.purpose = "assistants"
    f.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    return f


def make_refresh(template: MagicMock, attrs: tuple[str, ...] = _STORE_ATTRS) -> Any:
    """Return an async side_effect that copies attrs from *template* onto the target."""

    async def _refresh(obj: Any, **_kw: Any) -> None:
        for attr in attrs:
            setattr(obj, attr, getattr(template, attr))

    return _refresh


# ---------------------------------------------------------------------------
# Shared session / client fixtures
# ---------------------------------------------------------------------------


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
