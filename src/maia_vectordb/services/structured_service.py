"""Service layer for structured CSV query and preview operations."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DataError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.core.exceptions import DatabaseError, NotFoundError, ValidationError
from maia_vectordb.models.file import File
from maia_vectordb.schemas.structured import (
    PreviewColumn,
    PreviewResponse,
    QueryResponse,
)
from maia_vectordb.services.csv_ingestion import schema_name_for_store
from maia_vectordb.services.json_utils import to_json_safe
from maia_vectordb.services.sql_validator import (
    SQLValidationError,
    validate_and_prepare_sql,
)

logger = logging.getLogger(__name__)

# Maximum response payload size before truncation (bytes).
MAX_RESPONSE_BYTES = 100_000  # 100 KB


async def execute_structured_query(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
    sql: str,
) -> QueryResponse:
    """Validate and execute a read-only SQL query against CSV data.

    Parameters
    ----------
    session:
        Database session.
    vector_store_id:
        Vector store whose CSV schema to query.
    sql:
        Raw SQL string from the client (validated to be a safe SELECT).

    Returns
    -------
    QueryResponse
        Columns, rows, row count, and truncation flag.

    Raises
    ------
    ValidationError
        If the SQL fails validation (not a SELECT, references wrong table, etc.).
    DatabaseError
        If the query execution fails.
    """
    schema_name = schema_name_for_store(vector_store_id)

    try:
        prepared_sql = validate_and_prepare_sql(sql, schema_name)
    except SQLValidationError as exc:
        raise ValidationError(str(exc)) from exc

    try:
        await session.execute(text("SET LOCAL statement_timeout = '10000'"))
        result = await session.execute(text(prepared_sql))
    except (DataError, ProgrammingError) as exc:
        logger.warning("Invalid SQL for store %s: %s", vector_store_id, exc)
        raise ValidationError(
            "Query execution failed: invalid SQL or data types"
        ) from exc
    except Exception as exc:
        logger.exception("SQL execution failed for store %s", vector_store_id)
        raise DatabaseError("Query execution failed") from exc

    columns = list(result.keys())
    raw_rows = result.fetchall()

    rows: list[list[Any]] = []
    truncated = False
    accumulated_size = 0

    for raw_row in raw_rows:
        converted = [to_json_safe(v) for v in raw_row]
        row_json = json.dumps(converted, default=str)
        accumulated_size += len(row_json)

        if accumulated_size > MAX_RESPONSE_BYTES:
            truncated = True
            break

        rows.append(converted)

    return QueryResponse(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
    )


async def get_file_preview(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
    file_id: uuid.UUID,
    limit: int,
) -> PreviewResponse:
    """Preview the first N rows of a structured CSV file.

    Parameters
    ----------
    session:
        Database session.
    vector_store_id:
        Vector store that owns the file.
    file_id:
        File to preview.
    limit:
        Maximum number of rows to return.

    Returns
    -------
    PreviewResponse
        Column metadata and data rows.

    Raises
    ------
    NotFoundError
        If the file does not exist or belongs to a different store.
    ValidationError
        If the file does not contain structured CSV data.
    """
    file_record = await session.get(File, file_id)
    if file_record is None or file_record.vector_store_id != vector_store_id:
        raise NotFoundError("File not found")

    attrs = file_record.attributes or {}
    if not attrs.get("structured"):
        raise ValidationError("File does not contain structured CSV data.")

    structured = attrs["structured"]

    schema_name = schema_name_for_store(vector_store_id)

    row_query = text(
        f'SELECT data FROM "{schema_name}".csv_rows '
        f"WHERE file_id = :file_id ORDER BY row_id LIMIT :limit"
    )
    result = await session.execute(row_query, {"file_id": str(file_id), "limit": limit})
    raw_rows = result.fetchall()
    rows = [row[0] for row in raw_rows]

    count_query = text(
        f'SELECT COUNT(*) FROM "{schema_name}".csv_rows WHERE file_id = :file_id'
    )
    count_result = await session.execute(count_query, {"file_id": str(file_id)})
    total_rows = count_result.scalar_one()

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
