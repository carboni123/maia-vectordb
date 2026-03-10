"""CSV structured ingestion: DuckDB parsing and per-vector-store Postgres storage."""

from __future__ import annotations

import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any

import duckdb
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.services.csv_utils import map_duckdb_type, normalize_columns
from maia_vectordb.services.json_utils import to_json_safe

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSERT_BATCH_SIZE = 5000


# ---------------------------------------------------------------------------
# Pure / sync helpers
# ---------------------------------------------------------------------------


_to_json_safe = to_json_safe  # backward-compat alias for internal callers


def parse_csv_with_duckdb(
    csv_content: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse CSV text using DuckDB's ``read_csv_auto`` for type inference.

    Parameters
    ----------
    csv_content:
        Raw CSV text (including header row).

    Returns
    -------
    tuple[list[dict], list[dict]]
        ``(columns_metadata, rows)`` where each column dict contains
        ``normalized``, ``original_header``, ``inferred_type``, and
        optionally ``sample_values``.
    """
    tmp_path: str | None = None
    conn: duckdb.DuckDBPyConnection | None = None

    try:
        # Write to temp file — DuckDB's read_csv_auto works best with files.
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(csv_content)
            tmp_path = tmp.name

        # Use forward-slash path (DuckDB on Windows needs POSIX paths).
        posix_path = Path(tmp_path).as_posix()

        conn = duckdb.connect(":memory:")
        rel = conn.sql(f"SELECT * FROM read_csv_auto('{posix_path}')")

        raw_headers: list[str] = rel.columns
        raw_types = rel.types  # list[DuckDBPyType]; converted via str() below
        normalized_names = normalize_columns(raw_headers)

        # Fetch all rows as tuples.
        raw_rows: list[tuple[Any, ...]] = rel.fetchall()

        # ---- Build column metadata ----
        columns_metadata: list[dict[str, Any]] = []
        for idx, (norm, original, dtype) in enumerate(
            zip(normalized_names, raw_headers, raw_types)
        ):
            col_meta: dict[str, Any] = {
                "normalized": norm,
                "original_header": original,
                "inferred_type": map_duckdb_type(str(dtype)),
            }

            # Collect up to 3 distinct non-null sample values.
            seen_samples: list[Any] = []
            seen_set: set[Any] = set()
            for row in raw_rows:
                val = row[idx]
                if val is not None and val not in seen_set:
                    seen_samples.append(_to_json_safe(val))
                    seen_set.add(val)
                    if len(seen_samples) >= 3:
                        break

            if seen_samples:
                col_meta["sample_values"] = seen_samples

            columns_metadata.append(col_meta)

        # ---- Build row dicts ----
        rows: list[dict[str, Any]] = []
        for raw_row in raw_rows:
            row_dict: dict[str, Any] = {}
            for col_idx, col_name in enumerate(normalized_names):
                row_dict[col_name] = _to_json_safe(raw_row[col_idx])
            rows.append(row_dict)

        return columns_metadata, rows

    finally:
        if conn is not None:
            conn.close()
        if tmp_path is not None:
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass


def build_structured_metadata(
    columns: list[dict[str, Any]],
    row_count: int,
) -> dict[str, Any]:
    """Build the metadata dict stored on a structured CSV file record.

    The ``"structured"`` key holds a dict (truthy) with column metadata and
    row count.  Downstream code uses ``attrs.get("structured")`` both as a
    truthiness check *and* to access ``.get("columns")``, so the value
    **must** be a dict — not a plain boolean.

    Returns
    -------
    dict
        ``{"structured": {"table_name": "csv_rows",
        "row_count": row_count, "columns": columns}}``
    """
    return {
        "structured": {
            "table_name": "csv_rows",
            "row_count": row_count,
            "columns": columns,
        },
    }


# ---------------------------------------------------------------------------
# Async DB helpers (per-vector-store Postgres schema)
# ---------------------------------------------------------------------------


def schema_name_for_store(vector_store_id: uuid.UUID) -> str:
    """Derive the Postgres schema name for a vector store's CSV data."""
    return f"vs_{str(vector_store_id).replace('-', '_')}"


async def ensure_csv_schema(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
) -> str:
    """Create the per-vector-store schema and ``csv_rows`` table if needed.

    Parameters
    ----------
    session:
        Async database session.
    vector_store_id:
        UUID of the owning vector store.

    Returns
    -------
    str
        The schema name (e.g. ``vs_abcd1234_...``).
    """
    schema = schema_name_for_store(vector_store_id)

    await session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    await session.execute(
        text(
            f'CREATE TABLE IF NOT EXISTS "{schema}".csv_rows ('
            f"  file_id UUID NOT NULL,"
            f"  row_id BIGSERIAL NOT NULL,"
            f"  data JSONB NOT NULL,"
            f"  PRIMARY KEY (file_id, row_id)"
            f")"
        )
    )
    await session.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS idx_csv_rows_file_id "
            f'ON "{schema}".csv_rows (file_id)'
        )
    )
    await session.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS idx_csv_rows_data_gin "
            f'ON "{schema}".csv_rows USING GIN (data)'
        )
    )

    logger.info("Ensured CSV schema %s for vector store %s", schema, vector_store_id)
    return schema


async def insert_csv_rows(
    session: AsyncSession,
    schema_name: str,
    file_id: uuid.UUID,
    rows: list[dict[str, Any]],
) -> int:
    """Batch-insert parsed CSV rows into the per-vector-store table.

    Parameters
    ----------
    session:
        Async database session.
    schema_name:
        Target Postgres schema name.
    file_id:
        UUID of the file these rows belong to.
    rows:
        List of row dicts (normalized column names as keys).

    Returns
    -------
    int
        Total number of rows inserted.
    """
    total_inserted = 0

    for i in range(0, len(rows), INSERT_BATCH_SIZE):
        batch = rows[i : i + INSERT_BATCH_SIZE]
        values_list = [
            {"file_id": str(file_id), "data": json.dumps(row)} for row in batch
        ]
        await session.execute(
            text(
                f'INSERT INTO "{schema_name}".csv_rows (file_id, data) '
                f"VALUES (:file_id, CAST(:data AS jsonb))"
            ),
            values_list,
        )
        total_inserted += len(batch)

    logger.info(
        "Inserted %d CSV rows into %s for file %s",
        total_inserted,
        schema_name,
        file_id,
    )
    return total_inserted


async def delete_csv_rows_for_file(
    session: AsyncSession,
    schema_name: str,
    file_id: uuid.UUID,
) -> int:
    """Delete all CSV rows belonging to a specific file.

    Parameters
    ----------
    session:
        Async database session.
    schema_name:
        Target Postgres schema name.
    file_id:
        UUID of the file whose rows should be removed.

    Returns
    -------
    int
        Number of rows deleted.
    """
    result = await session.execute(
        text(f'DELETE FROM "{schema_name}".csv_rows WHERE file_id = :file_id'),
        {"file_id": str(file_id)},
    )
    deleted: int = result.rowcount  # type: ignore[attr-defined]
    logger.info(
        "Deleted %d CSV rows from %s for file %s", deleted, schema_name, file_id
    )
    return deleted


async def drop_csv_schema(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
) -> None:
    """Drop the entire per-vector-store CSV schema.

    Parameters
    ----------
    session:
        Async database session.
    vector_store_id:
        UUID of the vector store being removed.
    """
    schema = schema_name_for_store(vector_store_id)
    await session.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    logger.info("Dropped CSV schema %s for vector store %s", schema, vector_store_id)
