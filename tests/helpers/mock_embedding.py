"""Mock embedding provider for testing.

Returns deterministic, hash-based vectors without API calls.
"""

from __future__ import annotations

import hashlib
from typing import Sequence


class MockEmbeddingProvider:
    """Mock embedding provider for testing.

    Returns deterministic, hash-based vectors without API calls.
    """

    def __init__(self, dimension: int = 1536) -> None:
        self._dimension = dimension

    def embed_texts(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate deterministic fake embeddings based on text content.

        Uses SHA-256 hash of the text to generate consistent vectors.
        """
        if not texts:
            return []

        embeddings = []
        for text in texts:
            hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()

            embedding = []
            for i in range(self._dimension):
                byte_idx = i % len(hash_bytes)
                value = (hash_bytes[byte_idx] / 127.5) - 1.0
                embedding.append(value)

            magnitude = sum(x * x for x in embedding) ** 0.5
            if magnitude > 0:
                embedding = [x / magnitude for x in embedding]

            embeddings.append(embedding)

        return embeddings
