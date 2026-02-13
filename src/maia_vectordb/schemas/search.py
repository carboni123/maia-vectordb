"""Pydantic schemas for similarity search API endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request body for similarity search."""

    query: str
    max_results: int = Field(default=10, ge=1, le=100)
    filter: dict[str, Any] | None = None


class SearchResult(BaseModel):
    """A single search result with chunk content, score, and metadata."""

    file_id: str
    filename: str | None = None
    chunk_index: int
    content: str
    score: float
    metadata: dict[str, Any] | None = None


class SearchResponse(BaseModel):
    """Response body for similarity search (OpenAI format)."""

    object: str = Field(default="list")
    data: list["SearchResult"]
    search_query: str
