"""Integration tests: full create → upload → search flow with mocked deps."""

from __future__ import annotations

import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from maia_vectordb.models.file import FileStatus
from tests.conftest import _FILE_ATTRS, make_file, make_refresh, make_store


class TestCreateUploadSearchFlow:
    """End-to-end flow: create store → upload file → search."""

    @patch("maia_vectordb.api.search.embed_texts")
    @patch("maia_vectordb.api.files.embed_texts")
    @patch("maia_vectordb.api.files.split_text")
    def test_full_flow(
        self,
        mock_split: MagicMock,
        mock_file_embed: MagicMock,
        mock_search_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """Create a store, upload a file, then search — all succeed."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id, name="integration-store")

        # --- Step 1: Create vector store ---
        mock_session.refresh = AsyncMock(side_effect=make_refresh(store))

        resp = client.post("/v1/vector_stores", json={"name": "integration-store"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "integration-store"
        assert body["object"] == "vector_store"
        assert body["id"]  # ID is present

        # --- Step 2: Upload a file ---
        file_mock = make_file(
            vector_store_id=store_id,
            filename="test.txt",
            status=FileStatus.completed,
            byte_size=11,
        )
        mock_session.get = AsyncMock(return_value=store)
        mock_session.refresh = AsyncMock(
            side_effect=make_refresh(file_mock, _FILE_ATTRS)
        )

        mock_split.return_value = ["chunk one", "chunk two"]
        mock_file_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

        resp = client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={"file": ("test.txt", BytesIO(b"hello world"), "text/plain")},
        )
        assert resp.status_code == 201
        file_body = resp.json()
        assert file_body["status"] == "completed"
        assert file_body["chunk_count"] == 2
        assert file_body["object"] == "vector_store.file"

        # --- Step 3: Search ---
        mock_search_embed.return_value = [[0.1] * 1536]

        search_row = MagicMock()
        search_row.file_id = file_mock.id
        search_row.filename = "test.txt"
        search_row.chunk_index = 0
        search_row.content = "chunk one"
        search_row.score = 0.95
        search_row.chunk_metadata = None

        result_mock = MagicMock()
        result_mock.fetchall.return_value = [search_row]
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "hello", "max_results": 5},
        )
        assert resp.status_code == 200
        search_body = resp.json()
        assert search_body["object"] == "list"
        assert search_body["search_query"] == "hello"
        assert len(search_body["data"]) == 1
        assert search_body["data"][0]["content"] == "chunk one"
        assert search_body["data"][0]["score"] == 0.95

    @patch("maia_vectordb.api.search.embed_texts")
    @patch("maia_vectordb.api.files.embed_texts")
    @patch("maia_vectordb.api.files.split_text")
    def test_upload_then_get_file_status(
        self,
        mock_split: MagicMock,
        mock_embed: MagicMock,
        mock_search_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """Upload a file, then poll its status via GET."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        file_mock = make_file(
            vector_store_id=store_id,
            filename="poll.txt",
            status=FileStatus.completed,
            byte_size=5,
        )

        mock_session.get = AsyncMock(return_value=store)
        mock_session.refresh = AsyncMock(
            side_effect=make_refresh(file_mock, _FILE_ATTRS)
        )

        mock_split.return_value = ["content"]
        mock_embed.return_value = [[0.1] * 1536]

        # Upload
        resp = client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={"file": ("poll.txt", BytesIO(b"hello"), "text/plain")},
        )
        assert resp.status_code == 201
        file_id = resp.json()["id"]

        # GET file status
        mock_session.get = AsyncMock(side_effect=[store, file_mock])
        result_mock = MagicMock()
        result_mock.all.return_value = [("chunk_id",)]
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get(f"/v1/vector_stores/{store_id}/files/{file_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["chunk_count"] == 1

    def test_create_list_delete_flow(
        self,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """Create stores, list them, then delete one."""
        store1 = make_store(name="store-alpha")
        store2 = make_store(name="store-beta")

        # Create store 1
        mock_session.refresh = AsyncMock(side_effect=make_refresh(store1))
        resp = client.post("/v1/vector_stores", json={"name": "store-alpha"})
        assert resp.status_code == 201

        # Create store 2
        mock_session.refresh = AsyncMock(side_effect=make_refresh(store2))
        resp = client.post("/v1/vector_stores", json={"name": "store-beta"})
        assert resp.status_code == 201

        # List stores
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [store1, store2]
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/v1/vector_stores")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2

        # Delete store 1
        mock_session.get = AsyncMock(return_value=store1)
        resp = client.delete(f"/v1/vector_stores/{store1.id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert resp.json()["object"] == "vector_store.deleted"

    @patch("maia_vectordb.api.search.embed_texts")
    def test_search_empty_store(
        self,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """Searching an empty vector store returns empty results."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)

        # Create
        mock_session.refresh = AsyncMock(side_effect=make_refresh(store))
        resp = client.post("/v1/vector_stores", json={"name": "empty-store"})
        assert resp.status_code == 201

        # Search (no chunks exist)
        mock_session.get = AsyncMock(return_value=store)
        mock_embed.return_value = [[0.1] * 1536]

        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "anything"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []
