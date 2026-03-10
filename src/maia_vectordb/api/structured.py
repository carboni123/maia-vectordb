"""Structured CSV query and preview endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from maia_vectordb.api.deps import DBSession
from maia_vectordb.schemas.structured import (
    PreviewResponse,
    QueryRequest,
    QueryResponse,
)
from maia_vectordb.services import structured_service, vector_store_service

router = APIRouter(
    prefix="/v1/vector_stores/{vector_store_id}",
    tags=["structured"],
)


@router.post("/query", response_model=QueryResponse)
async def query_structured(
    vector_store_id: uuid.UUID,
    body: QueryRequest,
    session: DBSession,
) -> QueryResponse:
    """Execute a read-only SQL query against CSV data in a vector store.

    The query is validated to ensure it is a single SELECT statement that
    only references the ``csv_rows`` table. A statement timeout of 10 s
    is enforced and results are truncated if they exceed 100 KB.
    """
    await vector_store_service.get_vector_store(session, vector_store_id)
    return await structured_service.execute_structured_query(
        session, vector_store_id, body.sql
    )


@router.get(
    "/files/{file_id}/preview",
    response_model=PreviewResponse,
)
async def preview_file(
    vector_store_id: uuid.UUID,
    file_id: uuid.UUID,
    session: DBSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> PreviewResponse:
    """Preview the first N rows of a structured CSV file.

    Returns column metadata (original headers, inferred types) alongside
    the actual data rows stored in the ``csv_rows`` table.
    """
    await vector_store_service.get_vector_store(session, vector_store_id)
    return await structured_service.get_file_preview(
        session, vector_store_id, file_id, limit
    )
