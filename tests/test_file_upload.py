"""Tests for file upload and processing endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from maia_vectordb.db.engine import get_db_session
from maia_vectordb.main import app
from maia_vectordb.models.file import FileStatus
from maia_vectordb.models.vector_store import VectorStoreStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FILE_ATTRS = (
    "id",
    "vector_store_id",
    "filename",
    "status",
    "bytes",
    "purpose",
    "created_at",
)


def _make_store(store_id: uuid.UUID | None = None) -> MagicMock:
    """Create a mock VectorStore ORM instance."""
    store = MagicMock()
    store.id = store_id or uuid.uuid4()
    store.name = "test-store"
    store.metadata_ = None
    store.file_counts = None
    store.status = VectorStoreStatus.completed
    store.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    store.updated_at = datetime(2025, 1, 1, tzinfo=UTC)
    store.expires_at = None
    return store


def _make_file(
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_session() -> AsyncMock:
    """Return a mock async session."""
    return AsyncMock()


@pytest.fixture()
def client(mock_session: AsyncMock) -> Generator[TestClient, None, None]:
    """TestClient with the DB session overridden."""

    async def _override() -> Any:  # noqa: ANN401
        yield mock_session

    app.dependency_overrides[get_db_session] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /v1/vector_stores/{id}/files — file upload
# ---------------------------------------------------------------------------


class TestUploadFile:
    """Tests for the file upload endpoint."""

    def test_upload_returns_404_for_missing_store(
        self, client: TestClient, mock_session: AsyncMock
    ) -> None:
        """AC3: Returns meaningful error if vector store not found."""
        mock_session.get = AsyncMock(return_value=None)

        resp = client.post(
            f"/v1/vector_stores/{uuid.uuid4()}/files",
            files={
                "file": ("hello.txt", BytesIO(b"hello"), "text/plain"),
            },
        )
        assert resp.status_code == 404
        assert "Vector store not found" in resp.json()["error"]["message"]

    @patch("maia_vectordb.api.files.embed_texts")
    @patch("maia_vectordb.api.files.split_text")
    def test_upload_file_end_to_end(
        self,
        mock_split: MagicMock,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: AsyncMock,
    ) -> None:
        """AC1: File upload processes end-to-end."""
        store_id = uuid.uuid4()
        store = _make_store(store_id=store_id)
        file_mock = _make_file(
            vector_store_id=store_id,
            filename="hello.txt",
            status=FileStatus.completed,
        )

        mock_session.get = AsyncMock(return_value=store)

        async def _refresh(obj: Any, **_kw: Any) -> None:
            for attr in _FILE_ATTRS:
                setattr(obj, attr, getattr(file_mock, attr))

        mock_session.refresh = AsyncMock(side_effect=_refresh)

        mock_split.return_value = ["chunk one", "chunk two"]
        mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

        content = b"hello world"
        resp = client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={
                "file": ("hello.txt", BytesIO(content), "text/plain"),
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["object"] == "vector_store.file"
        assert body["status"] == "completed"
        assert body["chunk_count"] == 2
        assert body["filename"] == "hello.txt"

        # Verify session.add_all was called (bulk insert)
        mock_session.add_all.assert_called_once()

    @patch("maia_vectordb.api.files.embed_texts")
    @patch("maia_vectordb.api.files.split_text")
    def test_upload_raw_text(
        self,
        mock_split: MagicMock,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: AsyncMock,
    ) -> None:
        """Endpoint accepts raw text via form field."""
        store_id = uuid.uuid4()
        store = _make_store(store_id=store_id)
        file_mock = _make_file(
            vector_store_id=store_id,
            filename="raw_text.txt",
            status=FileStatus.completed,
            byte_size=9,
        )

        mock_session.get = AsyncMock(return_value=store)

        async def _refresh(obj: Any, **_kw: Any) -> None:
            for attr in _FILE_ATTRS:
                setattr(obj, attr, getattr(file_mock, attr))

        mock_session.refresh = AsyncMock(side_effect=_refresh)

        mock_split.return_value = ["some text"]
        mock_embed.return_value = [[0.1] * 1536]

        resp = client.post(
            f"/v1/vector_stores/{store_id}/files",
            data={"text": "some text"},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "completed"
        assert body["chunk_count"] == 1

    def test_upload_no_file_or_text_returns_400(
        self, client: TestClient, mock_session: AsyncMock
    ) -> None:
        """Returns 400 when neither file nor text is provided."""
        store = _make_store()
        mock_session.get = AsyncMock(return_value=store)

        resp = client.post(f"/v1/vector_stores/{store.id}/files")
        assert resp.status_code == 400
        assert "Provide either" in resp.json()["error"]["message"]

    @patch("maia_vectordb.api.files.embed_texts")
    @patch("maia_vectordb.api.files.split_text")
    def test_upload_returns_response_shape(
        self,
        mock_split: MagicMock,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: AsyncMock,
    ) -> None:
        """AC5: Response includes chunk count and processing status."""
        store_id = uuid.uuid4()
        store = _make_store(store_id=store_id)
        file_mock = _make_file(
            vector_store_id=store_id,
            status=FileStatus.completed,
            byte_size=5,
        )

        mock_session.get = AsyncMock(return_value=store)

        async def _refresh(obj: Any, **_kw: Any) -> None:
            for attr in _FILE_ATTRS:
                setattr(obj, attr, getattr(file_mock, attr))

        mock_session.refresh = AsyncMock(side_effect=_refresh)

        mock_split.return_value = ["a"]
        mock_embed.return_value = [[0.1] * 1536]

        resp = client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={
                "file": ("a.txt", BytesIO(b"hello"), "text/plain"),
            },
        )

        body = resp.json()
        required_keys = {
            "id",
            "object",
            "vector_store_id",
            "filename",
            "status",
            "bytes",
            "chunk_count",
            "purpose",
            "created_at",
        }
        assert required_keys.issubset(body.keys())
        assert isinstance(body["chunk_count"], int)
        assert body["status"] in ("completed", "in_progress", "failed")

    @patch("maia_vectordb.api.files.embed_texts")
    @patch("maia_vectordb.api.files.split_text")
    def test_bulk_insert_called_for_multiple_chunks(
        self,
        mock_split: MagicMock,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: AsyncMock,
    ) -> None:
        """AC2: Bulk insert for 100+ chunks."""
        store_id = uuid.uuid4()
        store = _make_store(store_id=store_id)
        file_mock = _make_file(
            vector_store_id=store_id,
            status=FileStatus.completed,
        )

        mock_session.get = AsyncMock(return_value=store)

        async def _refresh(obj: Any, **_kw: Any) -> None:
            for attr in _FILE_ATTRS:
                setattr(obj, attr, getattr(file_mock, attr))

        mock_session.refresh = AsyncMock(side_effect=_refresh)

        num_chunks = 150
        mock_split.return_value = [f"chunk {i}" for i in range(num_chunks)]
        mock_embed.return_value = [[0.1] * 1536 for _ in range(num_chunks)]

        resp = client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={
                "file": ("big.txt", BytesIO(b"x" * 100), "text/plain"),
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["chunk_count"] == 150

        # Single add_all call (bulk insert)
        mock_session.add_all.assert_called_once()
        chunk_objs = mock_session.add_all.call_args[0][0]
        assert len(chunk_objs) == 150


class TestUploadLargeFileBackground:
    """Tests for background task processing of large files."""

    @patch("maia_vectordb.api.files._process_file_background")
    @patch("maia_vectordb.api.files._BACKGROUND_THRESHOLD", 10)
    def test_large_file_returns_in_progress(
        self,
        mock_bg: MagicMock,
        client: TestClient,
        mock_session: AsyncMock,
    ) -> None:
        """AC4: Large files processed via background task."""
        store_id = uuid.uuid4()
        store = _make_store(store_id=store_id)
        file_mock = _make_file(
            vector_store_id=store_id,
            filename="large.txt",
            status=FileStatus.in_progress,
            byte_size=50,
        )

        mock_session.get = AsyncMock(return_value=store)

        async def _refresh(obj: Any, **_kw: Any) -> None:
            for attr in _FILE_ATTRS:
                setattr(obj, attr, getattr(file_mock, attr))

        mock_session.refresh = AsyncMock(side_effect=_refresh)

        content = b"x" * 50
        resp = client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={
                "file": (
                    "large.txt",
                    BytesIO(content),
                    "text/plain",
                ),
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "in_progress"
        assert body["chunk_count"] == 0
        # Verify background task was scheduled
        mock_bg.assert_called_once()


class TestUploadProcessingFailure:
    """Tests for error handling during processing."""

    @patch("maia_vectordb.api.files.embed_texts")
    @patch("maia_vectordb.api.files.split_text")
    def test_processing_failure_marks_file_failed(
        self,
        mock_split: MagicMock,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: AsyncMock,
    ) -> None:
        """File status set to failed when processing errors out."""
        store_id = uuid.uuid4()
        store = _make_store(store_id=store_id)
        file_mock = _make_file(
            vector_store_id=store_id,
            status=FileStatus.failed,
        )

        mock_session.get = AsyncMock(return_value=store)

        async def _refresh(obj: Any, **_kw: Any) -> None:
            for attr in _FILE_ATTRS:
                setattr(obj, attr, getattr(file_mock, attr))

        mock_session.refresh = AsyncMock(side_effect=_refresh)

        mock_split.return_value = ["chunk"]
        mock_embed.side_effect = RuntimeError("OpenAI down")

        resp = client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={
                "file": ("fail.txt", BytesIO(b"oops"), "text/plain"),
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "failed"
        assert body["chunk_count"] == 0


# ---------------------------------------------------------------------------
# GET /v1/vector_stores/{id}/files/{file_id}
# ---------------------------------------------------------------------------


class TestGetFile:
    """Tests for the file status retrieval endpoint."""

    def test_get_file_not_found(
        self, client: TestClient, mock_session: AsyncMock
    ) -> None:
        store = _make_store()
        # First get → store, second get → None (file)
        mock_session.get = AsyncMock(side_effect=[store, None])

        resp = client.get(f"/v1/vector_stores/{store.id}/files/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_file_returns_chunk_count(
        self, client: TestClient, mock_session: AsyncMock
    ) -> None:
        store_id = uuid.uuid4()
        store = _make_store(store_id=store_id)
        file_obj = _make_file(
            vector_store_id=store_id,
            status=FileStatus.completed,
        )

        mock_session.get = AsyncMock(side_effect=[store, file_obj])

        result_mock = MagicMock()
        result_mock.all.return_value = [("id1",), ("id2",), ("id3",)]
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get(f"/v1/vector_stores/{store_id}/files/{file_obj.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["chunk_count"] == 3
        assert body["status"] == "completed"

    def test_get_file_wrong_store_returns_404(
        self, client: TestClient, mock_session: AsyncMock
    ) -> None:
        """File belongs to a different store - 404."""
        store = _make_store()
        other_store_id = uuid.uuid4()
        file_obj = _make_file(vector_store_id=other_store_id)

        mock_session.get = AsyncMock(side_effect=[store, file_obj])

        resp = client.get(f"/v1/vector_stores/{store.id}/files/{file_obj.id}")
        assert resp.status_code == 404
