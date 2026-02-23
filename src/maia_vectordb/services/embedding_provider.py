"""Embedding provider abstraction for dependency injection and testing."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Protocol, Sequence

import openai

from maia_vectordb.core.config import settings

logger = logging.getLogger(__name__)

# OpenAI embeddings API supports up to 2048 inputs per request
_MAX_BATCH_SIZE = 2048

# Retry configuration
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 1.0  # seconds
_BACKOFF_FACTOR = 2.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers.

    This allows dependency injection and testing without real API calls.
    """

    def embed_texts(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Embed a sequence of texts.

        Parameters
        ----------
        texts:
            Strings to embed.
        model:
            Embedding model name (provider-specific).

        Returns
        -------
        list[list[float]]
            One embedding vector per input text, in the same order.
        """
        ...


class OpenAIEmbeddingProvider:
    """Production embedding provider using OpenAI API."""

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the OpenAI embedding provider.

        Parameters
        ----------
        api_key:
            OpenAI API key. If None, uses settings.openai_api_key.
        """
        self._api_key = api_key or settings.openai_api_key

    def _get_client(self) -> openai.OpenAI:
        """Build a synchronous OpenAI client."""
        return openai.OpenAI(api_key=self._api_key)

    def embed_texts(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Embed texts using OpenAI API with batching and retry logic.

        Parameters
        ----------
        texts:
            Strings to embed.
        model:
            Embedding model name (default from settings).

        Returns
        -------
        list[list[float]]
            One embedding vector per input text, in the same order.
        """
        if not texts:
            return []

        if model is None:
            model = settings.embedding_model

        client = self._get_client()
        all_embeddings: list[list[float]] = [[] for _ in texts]

        for batch_start in range(0, len(texts), _MAX_BATCH_SIZE):
            batch = list(texts[batch_start : batch_start + _MAX_BATCH_SIZE])
            response = self._call_with_retry(client, batch, model)

            # OpenAI returns embeddings sorted by index within the batch
            for item in sorted(response.data, key=lambda d: d.index):
                all_embeddings[batch_start + item.index] = list(item.embedding)

        return all_embeddings

    def _call_with_retry(
        self,
        client: openai.OpenAI,
        texts: list[str],
        model: str,
    ) -> openai.types.CreateEmbeddingResponse:
        """Call the OpenAI embeddings endpoint with exponential backoff retry."""
        backoff = _INITIAL_BACKOFF
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                return client.embeddings.create(
                    input=texts,
                    model=model,
                    dimensions=settings.embedding_dimension,
                )
            except openai.RateLimitError as exc:
                last_exc = exc
                logger.warning(
                    "Rate limited (429), attempt %d/%d — retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    backoff,
                )
            except openai.APIStatusError as exc:
                if exc.status_code in _RETRYABLE_STATUS_CODES:
                    last_exc = exc
                    logger.warning(
                        "Transient error %d, attempt %d/%d — retrying in %.1fs",
                        exc.status_code,
                        attempt + 1,
                        _MAX_RETRIES,
                        backoff,
                    )
                else:
                    raise
            except openai.APIConnectionError as exc:
                last_exc = exc
                logger.warning(
                    "Connection error, attempt %d/%d — retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    backoff,
                )

            time.sleep(backoff)
            backoff *= _BACKOFF_FACTOR

        # Exhausted retries
        assert last_exc is not None
        raise last_exc


class MockEmbeddingProvider:
    """Mock embedding provider for testing.

    Returns deterministic, hash-based vectors without API calls.
    """

    def __init__(self, dimension: int = 1536) -> None:
        """Initialize the mock embedding provider.

        Parameters
        ----------
        dimension:
            Dimension of the embedding vectors (default 1536 for OpenAI).
        """
        self._dimension = dimension

    def embed_texts(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate deterministic fake embeddings based on text content.

        Uses SHA-256 hash of the text to generate consistent vectors.

        Parameters
        ----------
        texts:
            Strings to embed.
        model:
            Ignored (for API compatibility).

        Returns
        -------
        list[list[float]]
            One embedding vector per input text, in the same order.
        """
        if not texts:
            return []

        embeddings = []
        for text in texts:
            # Generate deterministic hash-based embedding
            hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()

            # Expand hash to desired dimension using modular arithmetic
            embedding = []
            for i in range(self._dimension):
                # Use hash bytes cyclically to generate values
                byte_idx = i % len(hash_bytes)
                # Normalize to [-1, 1] range
                value = (hash_bytes[byte_idx] / 127.5) - 1.0
                embedding.append(value)

            # Normalize to unit vector for realistic embeddings
            magnitude = sum(x * x for x in embedding) ** 0.5
            if magnitude > 0:
                embedding = [x / magnitude for x in embedding]

            embeddings.append(embedding)

        return embeddings


_DEFAULT_PROVIDER: EmbeddingProvider | None = None


def set_default_provider(provider: EmbeddingProvider) -> None:
    """Set the default provider for dependency injection in tests.

    Parameters
    ----------
    provider:
        The provider instance to use as default.
    """
    global _DEFAULT_PROVIDER
    _DEFAULT_PROVIDER = provider


def get_embedding_provider(use_mock: bool | None = None) -> EmbeddingProvider:
    """Factory function to get the appropriate embedding provider.

    Parameters
    ----------
    use_mock:
        If True, returns MockEmbeddingProvider.
        If False, returns OpenAIEmbeddingProvider.
        If None, checks for injected provider, then settings.testing flag.

    Returns
    -------
    EmbeddingProvider
        The configured embedding provider instance.
    """
    # Allow test dependency injection
    if _DEFAULT_PROVIDER is not None:
        return _DEFAULT_PROVIDER

    if use_mock is None:
        # Check if we're in test mode
        use_mock = getattr(settings, "testing", False)

    if use_mock:
        return MockEmbeddingProvider()
    return OpenAIEmbeddingProvider()
