"""Pydantic schemas for similarity search API endpoints."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    """Request body for similarity search."""

    query: str
    max_results: int = Field(default=10, ge=1, le=100)
    filter: dict[str, Any] | None = None
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "query": "How does authentication work?",
                    "max_results": 5,
                    "filter": {"source": "docs"},
                    "score_threshold": 0.7,
                }
            ]
        },
    )


class SearchResult(BaseModel):
    """A single search result with chunk content, score, and metadata."""

    file_id: str
    filename: str | None = None
    chunk_index: int
    content: str
    score: float
    metadata: dict[str, Any] | None = None
    file_attributes: dict[str, Any] | None = None

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
