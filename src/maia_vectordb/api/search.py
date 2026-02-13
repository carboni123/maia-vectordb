"""Similarity search endpoint."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.db.engine import get_db_session
from maia_vectordb.models.vector_store import VectorStore
from maia_vectordb.schemas.search import SearchRequest, SearchResponse, SearchResult
from maia_vectordb.services.embedding import embed_texts

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/vector_stores/{vector_store_id}",
    tags=["search"],
)

DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def _validate_vector_store(
    session: AsyncSession, vector_store_id: uuid.UUID
) -> VectorStore:
    """Return the vector store or raise 404."""
    store = await session.get(VectorStore, vector_store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Vector store not found")
    return store


@router.post("/search", response_model=SearchResponse)
async def search(
    vector_store_id: uuid.UUID,
    body: SearchRequest,
    session: DBSession,
) -> Any:
    """Perform cosine similarity search over a vector store.

    Embeds the query string on-the-fly, searches using pgvector ``<=>``
    operator, applies optional metadata filters and score threshold, and
    returns top-k results ranked by similarity.
    """
    await _validate_vector_store(session, vector_store_id)

    # 1. Embed the query
    query_embedding = embed_texts([body.query])[0]

    # 2. Build the similarity search query
    #    pgvector <=> returns cosine *distance* (0 = identical, 2 = opposite).
    #    Convert to similarity: score = 1 - distance.
    params: dict[str, Any] = {
        "vector_store_id": vector_store_id,
        "query_embedding": str(query_embedding),
        "max_results": body.max_results,
    }

    where_clauses = [
        "fc.vector_store_id = :vector_store_id",
        "fc.embedding IS NOT NULL",
    ]

    # Metadata filters: each key-value pair becomes a JSON containment check
    if body.filter:
        for i, (key, value) in enumerate(body.filter.items()):
            param_key = f"filter_key_{i}"
            param_val = f"filter_val_{i}"
            where_clauses.append(f"fc.metadata->>:{param_key} = :{param_val}")
            params[param_key] = key
            params[param_val] = str(value)

    # Score threshold filter (applied as distance threshold)
    if body.score_threshold is not None:
        # score = 1 - distance, so distance < 1 - threshold
        where_clauses.append("(fc.embedding <=> :query_embedding) <= :max_distance")
        params["max_distance"] = 1.0 - body.score_threshold

    where_sql = " AND ".join(where_clauses)

    sql = text(f"""
        SELECT
            fc.id,
            fc.file_id,
            fc.chunk_index,
            fc.content,
            fc.metadata AS chunk_metadata,
            f.filename,
            (1 - (fc.embedding <=> :query_embedding)) AS score
        FROM file_chunks fc
        JOIN files f ON f.id = fc.file_id
        WHERE {where_sql}
        ORDER BY fc.embedding <=> :query_embedding
        LIMIT :max_results
    """)

    result = await session.execute(sql, params)
    rows = result.fetchall()

    data: list[SearchResult] = []
    for row in rows:
        data.append(
            SearchResult(
                file_id=str(row.file_id),
                filename=row.filename,
                chunk_index=row.chunk_index,
                content=row.content,
                score=round(float(row.score), 6),
                metadata=row.chunk_metadata,
            )
        )

    return SearchResponse(
        data=data,
        search_query=body.query,
    )
