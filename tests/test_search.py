"""Tests for the similarity search endpoint."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMBEDDING_DIM = 1536


def _make_search_row(
    *,
    file_id: uuid.UUID | None = None,
    filename: str = "doc.txt",
    chunk_index: int = 0,
    content: str = "hello world",
    score: float = 0.95,
    chunk_metadata: dict[str, Any] | None = None,
) -> Any:
    """Create a mock database row from the search SQL query."""
    row = MagicMock()
    row.file_id = file_id or uuid.uuid4()
    row.filename = filename
    row.chunk_index = chunk_index
    row.content = content
    row.score = score
    row.chunk_metadata = chunk_metadata
    return row


# ---------------------------------------------------------------------------
# POST /v1/vector_stores/{id}/search
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for the similarity search endpoint."""

    def test_search_returns_404_for_missing_store(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Returns 404 when vector store does not exist."""
        mock_session.get = AsyncMock(return_value=None)

        resp = client.post(
            f"/v1/vector_stores/{uuid.uuid4()}/search",
            json={"query": "hello"},
        )
        assert resp.status_code == 404
        assert "Vector store not found" in resp.json()["error"]["message"]

    @patch("maia_vectordb.api.search.embed_texts")
    def test_search_returns_ranked_results(
        self,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """AC1: Search returns top-k results ranked by cosine similarity."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)

        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]

        row1 = _make_search_row(content="best match", score=0.95, chunk_index=0)
        row2 = _make_search_row(content="second match", score=0.80, chunk_index=1)

        result_mock = MagicMock()
        result_mock.fetchall.return_value = [row1, row2]
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "test query", "max_results": 5},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "list"
        assert body["search_query"] == "test query"
        assert len(body["data"]) == 2

        # Verify ranking order (highest score first)
        assert body["data"][0]["score"] >= body["data"][1]["score"]
        assert body["data"][0]["content"] == "best match"
        assert body["data"][1]["content"] == "second match"

    @patch("maia_vectordb.api.search.embed_texts")
    def test_search_with_metadata_filter(
        self,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """AC2: Metadata filtering narrows results correctly."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)

        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]

        row = _make_search_row(
            content="filtered result",
            score=0.9,
            chunk_metadata={"category": "science"},
        )

        result_mock = MagicMock()
        result_mock.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "test",
                "filter": {"category": "science"},
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["metadata"] == {"category": "science"}

        # Verify the SQL was called with filter parameters
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0].text)
        assert "metadata" in sql_text
        params = call_args[0][1]
        assert params["filter_key_0"] == "category"
        assert params["filter_val_0"] == "science"

    @patch("maia_vectordb.api.search.embed_texts")
    def test_search_with_score_threshold(
        self,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """AC3: score_threshold excludes low-relevance results."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)

        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]

        # Only return high-score result (threshold filters in SQL)
        row = _make_search_row(content="relevant", score=0.9)
        result_mock = MagicMock()
        result_mock.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "test", "score_threshold": 0.8},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

        # Verify the SQL includes distance threshold
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0].text)
        assert "max_distance" in sql_text
        params = call_args[0][1]
        assert params["max_distance"] == pytest.approx(0.2)

    @patch("maia_vectordb.api.search.embed_texts")
    def test_search_generates_query_embedding(
        self,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """AC4: Query embedding generated on-the-fly via embed_texts."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)

        mock_embed.return_value = [[0.5] * _EMBEDDING_DIM]

        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "my query text"},
        )

        assert resp.status_code == 200
        mock_embed.assert_called_once_with(["my query text"])

    @patch("maia_vectordb.api.search.embed_texts")
    def test_search_response_shape(
        self,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """AC5: Response includes text content, score, and metadata."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)

        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]

        file_id = uuid.uuid4()
        row = _make_search_row(
            file_id=file_id,
            filename="notes.txt",
            chunk_index=3,
            content="The quick brown fox",
            score=0.87,
            chunk_metadata={"source": "wiki"},
        )
        result_mock = MagicMock()
        result_mock.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "fox"},
        )

        assert resp.status_code == 200
        body = resp.json()
        item = body["data"][0]

        # Verify all required fields are present
        assert item["file_id"] == str(file_id)
        assert item["filename"] == "notes.txt"
        assert item["chunk_index"] == 3
        assert item["content"] == "The quick brown fox"
        assert isinstance(item["score"], float)
        assert item["score"] == pytest.approx(0.87, abs=1e-4)
        assert item["metadata"] == {"source": "wiki"}

    @patch("maia_vectordb.api.search.embed_texts")
    def test_search_empty_results(
        self,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """Returns empty list when no chunks match."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)

        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]

        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "nonexistent topic"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["search_query"] == "nonexistent topic"

    @patch("maia_vectordb.api.search.embed_texts")
    def test_search_default_max_results(
        self,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """Default max_results is 10."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)

        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]

        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "test"},
        )

        assert resp.status_code == 200
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["max_results"] == 10

    @patch("maia_vectordb.api.search.embed_texts")
    def test_search_with_multiple_filters(
        self,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """Multiple metadata filters are combined with AND."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)

        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]

        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "test",
                "filter": {"category": "science", "lang": "en"},
            },
        )

        assert resp.status_code == 200
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0].text)
        # Both filter keys should appear in the SQL
        assert "filter_key_0" in sql_text
        assert "filter_key_1" in sql_text

    def test_search_missing_query_returns_422(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Missing query field returns validation error."""
        store_id = uuid.uuid4()
        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={},
        )
        assert resp.status_code == 422

    def test_search_invalid_score_threshold(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """score_threshold > 1.0 returns validation error."""
        store_id = uuid.uuid4()
        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "test", "score_threshold": 1.5},
        )
        assert resp.status_code == 422
