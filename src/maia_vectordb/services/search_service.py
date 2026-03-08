"""Service layer for similarity search operations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.schemas.search import SearchResult
from maia_vectordb.services.query_filters import build_metadata_clauses


async def similarity_search(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
    query_embedding: list[float],
    max_results: int,
    metadata_filter: dict[str, Any] | None = None,
    score_threshold: float | None = None,
) -> list[SearchResult]:
    """Run cosine similarity search over a vector store.

    Parameters
    ----------
    session:
        Database session.
    vector_store_id:
        Vector store to search within.
    query_embedding:
        Pre-computed embedding for the query text.
    max_results:
        Maximum number of results to return.
    metadata_filter:
        Optional metadata key-value filters.
    score_threshold:
        Minimum similarity score (0-1). Results below this are excluded.

    Returns
    -------
    list[SearchResult]
        Ranked search results with content, score, and metadata.
    """
    params: dict[str, Any] = {
        "vector_store_id": vector_store_id,
        "query_embedding": str(query_embedding),
        "max_results": max_results,
    }

    where_clauses = [
        "fc.vector_store_id = :vector_store_id",
        "fc.embedding IS NOT NULL",
    ]

    # Metadata filters via shared builder (parameterized)
    meta_clauses, meta_params = build_metadata_clauses(metadata_filter)
    where_clauses.extend(meta_clauses)
    params.update(meta_params)

    # Score threshold filter (applied as distance threshold)
    if score_threshold is not None:
        where_clauses.append("(fc.embedding <=> :query_embedding) <= :max_distance")
        params["max_distance"] = 1.0 - score_threshold

    where_sql = " AND ".join(where_clauses)

    sql = text(
        "SELECT "
        "  fc.id, fc.file_id, fc.chunk_index, fc.content, "
        "  fc.metadata AS chunk_metadata, "
        "  f.filename, f.attributes AS file_attributes, "
        "  (1 - (fc.embedding <=> :query_embedding)) AS score "
        "FROM file_chunks fc "
        "JOIN files f ON f.id = fc.file_id "
        f"WHERE {where_sql} "
        "ORDER BY fc.embedding <=> :query_embedding "
        "LIMIT :max_results"
    )

    result = await session.execute(sql, params)
    rows = result.fetchall()

    return [
        SearchResult(
            file_id=str(row.file_id),
            filename=row.filename,
            chunk_index=row.chunk_index,
            content=row.content,
            score=round(float(row.score), 6),
            metadata=row.chunk_metadata,
            file_attributes=row.file_attributes,
        )
        for row in rows
    ]
