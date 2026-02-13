"""Tests for the embedding service (no real API calls)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import openai

from maia_vectordb.services.embedding import (
    _INITIAL_BACKOFF,
    _MAX_BATCH_SIZE,
    _MAX_RETRIES,
    chunk_and_embed,
    embed_texts,
)


def _fake_embedding(dim: int = 1536) -> list[float]:
    return [0.1] * dim


def _make_response(
    texts: list[str],
) -> openai.types.CreateEmbeddingResponse:
    """Build a fake CreateEmbeddingResponse."""
    data = [
        openai.types.Embedding(
            embedding=_fake_embedding(),
            index=i,
            object="embedding",
        )
        for i in range(len(texts))
    ]
    return openai.types.CreateEmbeddingResponse(
        data=data,
        model="text-embedding-3-small",
        object="list",
        usage=openai.types.create_embedding_response.Usage(
            prompt_tokens=len(texts) * 5,
            total_tokens=len(texts) * 5,
        ),
    )


# ---------------------------------------------------------------------------
# AC 3: OpenAI API called with proper batching
# ---------------------------------------------------------------------------


class TestEmbedTexts:
    """embed_texts batches correctly and returns ordered results."""

    @patch("maia_vectordb.services.embedding._get_client")
    def test_single_batch(self, mock_get_client: MagicMock) -> None:
        """Small input uses a single API call."""
        texts = ["hello", "world"]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = _make_response(texts)
        mock_get_client.return_value = mock_client

        result = embed_texts(texts)
        assert len(result) == 2
        assert mock_client.embeddings.create.call_count == 1

    @patch("maia_vectordb.services.embedding._get_client")
    def test_multiple_batches(self, mock_get_client: MagicMock) -> None:
        """Input > _MAX_BATCH_SIZE is split into multiple API calls."""
        count = _MAX_BATCH_SIZE + 10
        texts = [f"text_{i}" for i in range(count)]

        mock_client = MagicMock()

        def side_effect(*, input: list[str], model: str) -> Any:  # noqa: A002
            return _make_response(input)

        mock_client.embeddings.create.side_effect = side_effect
        mock_get_client.return_value = mock_client

        result = embed_texts(texts)
        assert len(result) == count
        assert mock_client.embeddings.create.call_count == 2

    @patch("maia_vectordb.services.embedding._get_client")
    def test_empty_input(self, mock_get_client: MagicMock) -> None:
        """Empty input returns empty list without calling API."""
        result = embed_texts([])
        assert result == []
        mock_get_client.assert_not_called()

    def test_batch_size_constant(self) -> None:
        """Batch size is 2048 per spec."""
        assert _MAX_BATCH_SIZE == 2048


# ---------------------------------------------------------------------------
# AC 4: Retry logic handles rate limits (429) and transient errors
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Retry with exponential backoff on 429 and transient errors."""

    @patch("maia_vectordb.services.embedding.time.sleep")
    @patch("maia_vectordb.services.embedding._get_client")
    def test_retries_on_rate_limit(
        self, mock_get_client: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """429 triggers retry, then succeeds."""
        texts = ["hello"]
        mock_client = MagicMock()

        response = MagicMock()
        response.status_code = 429
        response.headers = {}

        calls = 0

        def side_effect(*, input: list[str], model: str) -> Any:  # noqa: A002
            nonlocal calls
            calls += 1
            if calls == 1:
                raise openai.RateLimitError(
                    message="rate limited",
                    response=response,
                    body=None,
                )
            return _make_response(input)

        mock_client.embeddings.create.side_effect = side_effect
        mock_get_client.return_value = mock_client

        result = embed_texts(texts)
        assert len(result) == 1
        assert mock_sleep.call_count == 1
        # First retry waits _INITIAL_BACKOFF seconds
        mock_sleep.assert_called_with(_INITIAL_BACKOFF)

    @patch("maia_vectordb.services.embedding.time.sleep")
    @patch("maia_vectordb.services.embedding._get_client")
    def test_retries_on_server_error(
        self, mock_get_client: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """500 triggers retry."""
        texts = ["hello"]
        mock_client = MagicMock()

        response = MagicMock()
        response.status_code = 500
        response.headers = {}

        calls = 0

        def side_effect(*, input: list[str], model: str) -> Any:  # noqa: A002
            nonlocal calls
            calls += 1
            if calls == 1:
                raise openai.InternalServerError(
                    message="server error",
                    response=response,
                    body=None,
                )
            return _make_response(input)

        mock_client.embeddings.create.side_effect = side_effect
        mock_get_client.return_value = mock_client

        result = embed_texts(texts)
        assert len(result) == 1
        assert mock_sleep.call_count == 1

    @patch("maia_vectordb.services.embedding.time.sleep")
    @patch("maia_vectordb.services.embedding._get_client")
    def test_exhausted_retries_raises(
        self, mock_get_client: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """After _MAX_RETRIES failures, the last exception is raised."""
        texts = ["hello"]
        mock_client = MagicMock()

        response = MagicMock()
        response.status_code = 429
        response.headers = {}

        mock_client.embeddings.create.side_effect = openai.RateLimitError(
            message="rate limited",
            response=response,
            body=None,
        )
        mock_get_client.return_value = mock_client

        try:
            embed_texts(texts)
            raise AssertionError("Expected RateLimitError")
        except openai.RateLimitError:
            pass

        assert mock_sleep.call_count == _MAX_RETRIES

    @patch("maia_vectordb.services.embedding.time.sleep")
    @patch("maia_vectordb.services.embedding._get_client")
    def test_non_retryable_error_raises_immediately(
        self, mock_get_client: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """Non-retryable status codes raise immediately."""
        texts = ["hello"]
        mock_client = MagicMock()

        response = MagicMock()
        response.status_code = 401
        response.headers = {}

        mock_client.embeddings.create.side_effect = openai.AuthenticationError(
            message="invalid api key",
            response=response,
            body=None,
        )
        mock_get_client.return_value = mock_client

        try:
            embed_texts(texts)
            raise AssertionError("Expected AuthenticationError")
        except openai.AuthenticationError:
            pass

        mock_sleep.assert_not_called()

    @patch("maia_vectordb.services.embedding.time.sleep")
    @patch("maia_vectordb.services.embedding._get_client")
    def test_exponential_backoff(
        self, mock_get_client: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """Backoff doubles each retry."""
        texts = ["hello"]
        mock_client = MagicMock()

        response = MagicMock()
        response.status_code = 429
        response.headers = {}

        calls = 0

        def side_effect(*, input: list[str], model: str) -> Any:  # noqa: A002
            nonlocal calls
            calls += 1
            if calls <= 3:
                raise openai.RateLimitError(
                    message="rate limited",
                    response=response,
                    body=None,
                )
            return _make_response(input)

        mock_client.embeddings.create.side_effect = side_effect
        mock_get_client.return_value = mock_client

        result = embed_texts(texts)
        assert len(result) == 1
        # backoff: 1.0, 2.0, 4.0
        sleep_values = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_values == [1.0, 2.0, 4.0]

    @patch("maia_vectordb.services.embedding.time.sleep")
    @patch("maia_vectordb.services.embedding._get_client")
    def test_retries_on_connection_error(
        self, mock_get_client: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """Connection errors trigger retry."""
        texts = ["hello"]
        mock_client = MagicMock()

        calls = 0

        def side_effect(*, input: list[str], model: str) -> Any:  # noqa: A002
            nonlocal calls
            calls += 1
            if calls == 1:
                raise openai.APIConnectionError(request=MagicMock())
            return _make_response(input)

        mock_client.embeddings.create.side_effect = side_effect
        mock_get_client.return_value = mock_client

        result = embed_texts(texts)
        assert len(result) == 1
        assert mock_sleep.call_count == 1


# ---------------------------------------------------------------------------
# chunk_and_embed integration (mocked embedding)
# ---------------------------------------------------------------------------


class TestChunkAndEmbed:
    """chunk_and_embed splits text and embeds each chunk."""

    @patch("maia_vectordb.services.embedding._get_client")
    def test_returns_tuples(self, mock_get_client: MagicMock) -> None:
        """Returns (chunk_text, embedding) tuples."""
        mock_client = MagicMock()

        def side_effect(*, input: list[str], model: str) -> Any:  # noqa: A002
            return _make_response(input)

        mock_client.embeddings.create.side_effect = side_effect
        mock_get_client.return_value = mock_client

        result = chunk_and_embed("Hello world", chunk_size=800, chunk_overlap=200)
        assert len(result) == 1
        text, vec = result[0]
        assert text == "Hello world"
        assert len(vec) == 1536

    @patch("maia_vectordb.services.embedding._get_client")
    def test_empty_text(self, mock_get_client: MagicMock) -> None:
        """Empty text returns empty list."""
        result = chunk_and_embed("", chunk_size=800, chunk_overlap=200)
        assert result == []
