"""Tests for embedding provider abstraction."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import openai

from maia_vectordb.services.embedding_provider import (
    EmbeddingProvider,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)


def _make_response(
    texts: list[str],
) -> openai.types.CreateEmbeddingResponse:
    """Build a fake CreateEmbeddingResponse."""
    data = [
        openai.types.Embedding(
            embedding=[0.1] * 1536,
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


class TestEmbeddingProvider:
    """Test that EmbeddingProvider protocol is defined correctly."""

    def test_protocol_exists(self) -> None:
        """EmbeddingProvider protocol can be imported."""
        assert EmbeddingProvider is not None


class TestMockEmbeddingProvider:
    """Test MockEmbeddingProvider returns deterministic vectors."""

    def test_returns_correct_dimension(self) -> None:
        """MockEmbeddingProvider returns vectors of correct dimension."""
        provider = MockEmbeddingProvider(dimension=1536)
        result = provider.embed_texts(["hello", "world"])

        assert len(result) == 2
        assert len(result[0]) == 1536
        assert len(result[1]) == 1536

    def test_deterministic_output(self) -> None:
        """Same text produces same embedding every time."""
        provider = MockEmbeddingProvider()
        text = "test message"

        result1 = provider.embed_texts([text])[0]
        result2 = provider.embed_texts([text])[0]

        assert result1 == result2

    def test_different_texts_different_embeddings(self) -> None:
        """Different texts produce different embeddings."""
        provider = MockEmbeddingProvider()

        result1 = provider.embed_texts(["hello"])[0]
        result2 = provider.embed_texts(["world"])[0]

        assert result1 != result2

    def test_normalized_vectors(self) -> None:
        """Embeddings are normalized to unit vectors."""
        provider = MockEmbeddingProvider()
        embedding = provider.embed_texts(["test"])[0]

        # Calculate magnitude
        magnitude = sum(x * x for x in embedding) ** 0.5

        # Should be approximately 1.0
        assert abs(magnitude - 1.0) < 1e-6

    def test_empty_input(self) -> None:
        """Empty input returns empty list."""
        provider = MockEmbeddingProvider()
        result = provider.embed_texts([])
        assert result == []

    def test_custom_dimension(self) -> None:
        """Can create provider with custom dimension."""
        provider = MockEmbeddingProvider(dimension=512)
        result = provider.embed_texts(["test"])

        assert len(result[0]) == 512

    def test_model_parameter_ignored(self) -> None:
        """model parameter is accepted but ignored."""
        provider = MockEmbeddingProvider()
        result = provider.embed_texts(["test"], model="custom-model")

        assert len(result) == 1
        assert len(result[0]) == 1536


class TestOpenAIEmbeddingProvider:
    """Test OpenAIEmbeddingProvider wraps existing logic."""

    @patch("maia_vectordb.services.embedding_provider.openai.OpenAI")
    def test_uses_openai_client(self, mock_openai_class: MagicMock) -> None:
        """OpenAIEmbeddingProvider uses OpenAI client."""
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = _make_response(["hello"])
        mock_openai_class.return_value = mock_client

        provider = OpenAIEmbeddingProvider(api_key="test-key")
        result = provider.embed_texts(["hello"])

        assert len(result) == 1
        assert len(result[0]) == 1536
        mock_client.embeddings.create.assert_called_once()

    @patch("maia_vectordb.services.embedding_provider.openai.OpenAI")
    def test_batching(self, mock_openai_class: MagicMock) -> None:
        """OpenAIEmbeddingProvider batches large inputs."""
        mock_client = MagicMock()

        def side_effect(
            *,
            input: list[str],
            model: str,  # noqa: A002
            **kwargs: Any,
        ) -> openai.types.CreateEmbeddingResponse:
            return _make_response(input)

        mock_client.embeddings.create.side_effect = side_effect
        mock_openai_class.return_value = mock_client

        provider = OpenAIEmbeddingProvider(api_key="test-key")
        # Create input larger than batch size (2048)
        texts = [f"text_{i}" for i in range(2060)]
        result = provider.embed_texts(texts)

        assert len(result) == 2060
        # Should have made 2 API calls (2048 + 12)
        assert mock_client.embeddings.create.call_count == 2

    @patch("maia_vectordb.services.embedding_provider.openai.OpenAI")
    def test_empty_input(self, mock_openai_class: MagicMock) -> None:
        """Empty input returns empty list without API call."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = OpenAIEmbeddingProvider(api_key="test-key")
        result = provider.embed_texts([])

        assert result == []
        mock_client.embeddings.create.assert_not_called()

    @patch("maia_vectordb.services.embedding_provider.openai.OpenAI")
    @patch("maia_vectordb.services.embedding_provider.time.sleep")
    def test_retry_on_rate_limit(
        self, mock_sleep: MagicMock, mock_openai_class: MagicMock
    ) -> None:
        """Provider retries on rate limit errors."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        response = MagicMock()
        response.status_code = 429
        response.headers = {}

        calls = 0

        def side_effect(
            *,
            input: list[str],
            model: str,  # noqa: A002
            **kwargs: Any,
        ) -> openai.types.CreateEmbeddingResponse:
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

        provider = OpenAIEmbeddingProvider(api_key="test-key")
        result = provider.embed_texts(["test"])

        assert len(result) == 1
        assert mock_sleep.call_count == 1


class TestGetEmbeddingProvider:
    """Test get_embedding_provider factory function."""

    def test_returns_openai_by_default(self) -> None:
        """Factory returns OpenAI provider by default."""
        provider = get_embedding_provider(use_mock=False)
        assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_returns_mock_when_requested(self) -> None:
        """Factory returns Mock provider when requested."""
        provider = get_embedding_provider(use_mock=True)
        assert isinstance(provider, MockEmbeddingProvider)

    def test_mock_provider_works(self) -> None:
        """Mock provider from factory works correctly."""
        provider = get_embedding_provider(use_mock=True)
        result = provider.embed_texts(["test"])

        assert len(result) == 1
        assert len(result[0]) == 1536
