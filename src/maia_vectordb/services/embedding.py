"""OpenAI embedding service with batching and retry logic."""

from __future__ import annotations

import logging
import time
from typing import Sequence

import openai

from maia_vectordb.core.config import settings
from maia_vectordb.services.chunking import split_text

logger = logging.getLogger(__name__)

# OpenAI embeddings API supports up to 2048 inputs per request
_MAX_BATCH_SIZE = 2048

# Retry configuration
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 1.0  # seconds
_BACKOFF_FACTOR = 2.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _get_client() -> openai.OpenAI:
    """Build a synchronous OpenAI client from settings."""
    return openai.OpenAI(api_key=settings.openai_api_key)


def embed_texts(
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
        response = _call_with_retry(client, batch, model)

        # OpenAI returns embeddings sorted by index within the batch
        for item in sorted(response.data, key=lambda d: d.index):
            all_embeddings[batch_start + item.index] = list(item.embedding)

    return all_embeddings


def _call_with_retry(
    client: openai.OpenAI,
    texts: list[str],
    model: str,
) -> openai.types.CreateEmbeddingResponse:
    """Call the OpenAI embeddings endpoint with exponential backoff retry."""
    backoff = _INITIAL_BACKOFF
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            return client.embeddings.create(input=texts, model=model)
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


def chunk_and_embed(
    text: str,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    model: str | None = None,
) -> list[tuple[str, list[float]]]:
    """Split text into chunks and generate embeddings for each.

    Parameters
    ----------
    text:
        Full document text.
    chunk_size:
        Max tokens per chunk.
    chunk_overlap:
        Overlap tokens between consecutive chunks.
    model:
        Embedding model name.

    Returns
    -------
    list[tuple[str, list[float]]]
        ``(chunk_text, embedding_vector)`` pairs.
    """
    chunks = split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        return []

    embeddings = embed_texts(chunks, model=model)
    return list(zip(chunks, embeddings, strict=True))
