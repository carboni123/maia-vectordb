"""Tests for the /v1/embeddings endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

_EMBEDDING_DIM = 1536


class TestCreateEmbeddings:
    """Tests for POST /v1/embeddings."""

    @patch("maia_vectordb.api.embeddings.embed_texts")
    def test_single_input(self, mock_embed: MagicMock, client: TestClient) -> None:
        """Returns one embedding vector for a single input string."""
        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]

        resp = client.post("/v1/embeddings", json={"input": ["hello"]})

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert len(body["data"][0]) == _EMBEDDING_DIM
        mock_embed.assert_called_once_with(["hello"])

    @patch("maia_vectordb.api.embeddings.embed_texts")
    def test_multiple_inputs(self, mock_embed: MagicMock, client: TestClient) -> None:
        """Returns one embedding per input string, in order."""
        texts = ["alpha", "bravo", "charlie"]
        mock_embed.return_value = [[float(i)] * _EMBEDDING_DIM for i in range(3)]

        resp = client.post("/v1/embeddings", json={"input": texts})

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 3
        mock_embed.assert_called_once_with(texts)

    def test_empty_input_returns_422(self, client: TestClient) -> None:
        """Empty input list is rejected by min_length=1 validation."""
        resp = client.post("/v1/embeddings", json={"input": []})
        assert resp.status_code == 422

    def test_missing_input_returns_422(self, client: TestClient) -> None:
        """Missing input field returns validation error."""
        resp = client.post("/v1/embeddings", json={})
        assert resp.status_code == 422

    def test_too_many_inputs_returns_422(self, client: TestClient) -> None:
        """More than 64 inputs is rejected by max_length=64 validation."""
        resp = client.post(
            "/v1/embeddings", json={"input": [f"text_{i}" for i in range(65)]}
        )
        assert resp.status_code == 422

    @patch("maia_vectordb.api.embeddings.embed_texts")
    def test_max_allowed_inputs(
        self, mock_embed: MagicMock, client: TestClient
    ) -> None:
        """Exactly 64 inputs is accepted (boundary)."""
        texts = [f"text_{i}" for i in range(64)]
        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM for _ in range(64)]

        resp = client.post("/v1/embeddings", json={"input": texts})

        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 64

    @patch("maia_vectordb.api.embeddings.embed_texts")
    def test_embed_texts_error_returns_500(
        self, mock_embed: MagicMock, client: TestClient
    ) -> None:
        """Upstream embed_texts failure surfaces as 500."""
        mock_embed.side_effect = RuntimeError("OpenAI unavailable")

        resp = client.post("/v1/embeddings", json={"input": ["hello"]})

        assert resp.status_code == 500

    @patch("maia_vectordb.api.embeddings.embed_texts")
    def test_response_shape(self, mock_embed: MagicMock, client: TestClient) -> None:
        """Response body has exactly the 'data' key with nested float lists."""
        mock_embed.return_value = [[0.5, 0.6, 0.7]]

        resp = client.post("/v1/embeddings", json={"input": ["test"]})

        body = resp.json()
        assert set(body.keys()) == {"data"}
        assert body["data"] == [[0.5, 0.6, 0.7]]
