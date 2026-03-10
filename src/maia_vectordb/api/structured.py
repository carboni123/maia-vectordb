"""Structured CSV query and preview endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import text

from maia_vectordb.api.deps import DBSession
from maia_vectordb.core.exceptions import NotFoundError, ValidationError
from maia_vectordb.models.file import File
from maia_vectordb.schemas.structured import (
    PreviewColumn,
    PreviewResponse,
    QueryRequest,
    QueryResponse,
)
from maia_vectordb.services import vector_store_service
from maia_vectordb.services.csv_ingestion import schema_name_for_store
from maia_vectordb.services.sql_validator import (
    SQLValidationError,
    validate_and_prepare_sql,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/vector_stores/{vector_store_id}",
    tags=["structured"],
)

# Maximum response payload size before truncation (bytes).
_MAX_RESPONSE_BYTES = 100_000  # 100 KB


def _to_json_safe(value: Any) -> Any:
    """Convert a database value to a JSON-serializable Python type."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        # Preserve integers; use float for fractional decimals.
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


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
    # 1. Verify vector store exists.
    await vector_store_service.get_vector_store(session, vector_store_id)

    # 2. Build schema name from vector store ID.
    schema_name = schema_name_for_store(vector_store_id)

    # 3. Validate and prepare SQL.
    try:
        prepared_sql = validate_and_prepare_sql(body.sql, schema_name)
    except SQLValidationError as exc:
        raise ValidationError(str(exc)) from exc

    # 4. Execute with a statement timeout to prevent long-running queries.
    try:
        await session.execute(text("SET LOCAL statement_timeout = '10000'"))
        result = await session.execute(text(prepared_sql))
    except Exception as exc:
        raise ValidationError(f"SQL execution error: {exc}") from exc

    # 5. Extract column names and rows.
    columns = list(result.keys())
    raw_rows = result.fetchall()

    # 6. Convert to JSON-safe values and track payload size.
    rows: list[list[Any]] = []
    truncated = False
    accumulated_size = 0

    for raw_row in raw_rows:
        converted = [_to_json_safe(v) for v in raw_row]
        row_json = json.dumps(converted, default=str)
        accumulated_size += len(row_json)

        if accumulated_size > _MAX_RESPONSE_BYTES:
            truncated = True
            break

        rows.append(converted)

    return QueryResponse(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
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
    # 1. Verify vector store exists.
    await vector_store_service.get_vector_store(session, vector_store_id)

    # 2. Get the file record.
    file_record = await session.get(File, file_id)
    if file_record is None or file_record.vector_store_id != vector_store_id:
        raise NotFoundError("File not found")

    # 3. Verify the file has structured metadata.
    attrs = file_record.attributes or {}
    if not attrs.get("structured"):
        raise ValidationError("File does not contain structured CSV data.")

    structured = attrs["structured"]

    # 4. Build schema name and query rows.
    schema_name = schema_name_for_store(vector_store_id)

    row_query = text(
        f'SELECT data FROM "{schema_name}".csv_rows '
        f"WHERE file_id = :file_id ORDER BY row_id LIMIT :limit"
    )
    result = await session.execute(row_query, {"file_id": str(file_id), "limit": limit})
    raw_rows = result.fetchall()
    rows = [row[0] for row in raw_rows]

    # 5. Get total row count.
    count_query = text(
        f'SELECT COUNT(*) FROM "{schema_name}".csv_rows WHERE file_id = :file_id'
    )
    count_result = await session.execute(count_query, {"file_id": str(file_id)})
    total_rows = count_result.scalar_one()

    # 6. Build column metadata from file attributes.
    columns_meta: list[PreviewColumn] = []
    for col in structured.get("columns", []):
        columns_meta.append(
            PreviewColumn(
                normalized=col["normalized"],
                original_header=col["original_header"],
                inferred_type=col["inferred_type"],
                sample_values=col.get("sample_values"),
            )
        )

    return PreviewResponse(
        columns=columns_meta,
        rows=rows,
        total_rows=total_rows,
    )
