"""Pydantic schemas for similarity search API endpoints."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SearchMode(str, Enum):
    """Available search strategies."""

    VECTOR = "vector"
    HYBRID = "hybrid"


class RankingWeights(BaseModel):
    """Relative weights for vector vs text fusion (auto-normalized)."""

    vector: float = Field(default=0.7, ge=0.0, le=1.0)
    text: float = Field(default=0.3, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def reject_all_zero(self) -> RankingWeights:
        """At least one weight must be positive."""
        if self.vector == 0.0 and self.text == 0.0:
            raise ValueError(
                "At least one ranking weight (vector or text) must be > 0."
            )
        return self


class SearchRequest(BaseModel):
    """Request body for similarity search."""

    query: str = Field(min_length=1)
    query_embedding: list[float] | None = Field(
        default=None,
        description="Pre-computed embedding vector. When provided, the server "
        "skips embedding generation and uses this vector directly.",
    )
    max_results: int = Field(default=10, ge=1, le=100)
    filter: dict[str, Any] | None = None
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    search_mode: SearchMode = SearchMode.VECTOR
    ranking_weights: RankingWeights | None = None
    half_life_days: float = Field(default=30.0, gt=0.0)
    mmr_lambda: float = Field(default=0.7, ge=0.0, le=1.0)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "query": "How does authentication work?",
                    "max_results": 5,
                    "filter": {"source": "docs"},
                    "score_threshold": 0.7,
                },
                {
                    "query": "latest deployment changes",
                    "max_results": 10,
                    "search_mode": "hybrid",
                    "ranking_weights": {"vector": 0.6, "text": 0.4},
                    "half_life_days": 14,
                    "mmr_lambda": 0.6,
                },
            ]
        },
    )


class ScoreDetails(BaseModel):
    """Breakdown of individual scoring signals (hybrid mode only)."""

    vector: float = 0.0
    text: float = 0.0
    temporal: float = 1.0


class SearchResult(BaseModel):
    """A single search result with chunk content, score, and metadata."""

    file_id: str
    filename: str | None = None
    chunk_index: int
    content: str
    score: float
    metadata: dict[str, Any] | None = None
    file_attributes: dict[str, Any] | None = None
    score_details: ScoreDetails | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "file_id": "660e8400-e29b-41d4-a716-446655440001",
                    "filename": "auth-guide.txt",
                    "chunk_index": 2,
                    "content": "Authentication uses JWT tokens issued by...",
                    "score": 0.92,
                    "metadata": {"source": "docs"},
                    "file_attributes": {"department": "engineering"},
                }
            ]
        },
    )


class SearchResponse(BaseModel):
    """Response body for similarity search (OpenAI format)."""

    object: str = Field(default="list")
    data: list["SearchResult"]
    search_query: str
    search_mode: SearchMode = SearchMode.VECTOR

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "object": "list",
                    "data": [
                        {
                            "file_id": "660e8400-e29b-41d4-a716-446655440001",
                            "filename": "auth-guide.txt",
                            "chunk_index": 2,
                            "content": "Authentication uses JWT tokens issued by...",
                            "score": 0.92,
                            "metadata": {"source": "docs"},
                        }
                    ],
                    "search_query": "How does authentication work?",
                }
            ]
        },
    )
