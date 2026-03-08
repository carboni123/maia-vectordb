"""OpenAI embedding service with batching and retry logic."""

from __future__ import annotations

import asyncio
import logging
from typing import Sequence

import openai

from maia_vectordb.core.config import settings

logger = logging.getLogger(__name__)

# OpenAI embeddings API supports up to 2048 inputs per request
_MAX_BATCH_SIZE = 2048

# Retry configuration
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 1.0  # seconds
_BACKOFF_FACTOR = 2.0
_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


_client: openai.AsyncOpenAI | None = None


def _get_client() -> openai.AsyncOpenAI:
    """Return a lazily-initialised singleton AsyncOpenAI client."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def embed_texts(
    texts: Sequence[str],
    *,
    model: str | None = None,
) -> list[list[float]]:
    """Embed a sequence of texts with batching and retry logic.

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

    client = _get_client()
    all_embeddings: list[list[float]] = [[] for _ in texts]

    for batch_start in range(0, len(texts), _MAX_BATCH_SIZE):
        batch = list(texts[batch_start : batch_start + _MAX_BATCH_SIZE])
        response = await _call_with_retry(client, batch, model)

        # OpenAI returns embeddings sorted by index within the batch
        for item in sorted(response.data, key=lambda d: d.index):
            all_embeddings[batch_start + item.index] = list(item.embedding)

    return all_embeddings


async def _call_with_retry(
    client: openai.AsyncOpenAI,
    texts: list[str],
    model: str,
) -> openai.types.CreateEmbeddingResponse:
    """Call the OpenAI embeddings endpoint with exponential backoff retry."""
    backoff = _INITIAL_BACKOFF
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            return await client.embeddings.create(
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

        await asyncio.sleep(backoff)
        backoff *= _BACKOFF_FACTOR

    # Exhausted retries — last_exc is always set after the loop
    if last_exc is None:
        raise RuntimeError("embed_texts retry loop ended without an exception")
    raise last_exc
