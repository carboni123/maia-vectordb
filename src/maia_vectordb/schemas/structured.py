"""Schemas for structured CSV query endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request body for executing a read-only SQL query against CSV data."""

    sql: str = Field(..., description="SQL SELECT query to execute", max_length=10_000)


class QueryResponse(BaseModel):
    """Response from a structured SQL query execution."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool


class PreviewColumn(BaseModel):
    """Metadata about a single column in a structured CSV file."""

    normalized: str
    original_header: str
    inferred_type: str
    sample_values: list[Any] | None = None


class PreviewResponse(BaseModel):
    """Response from previewing rows in a structured CSV file."""

    columns: list[PreviewColumn]
    rows: list[dict[str, Any]]
    total_rows: int
