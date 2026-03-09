"""CSV column normalization and DuckDB-to-Postgres type mapping utilities."""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# DuckDB → Postgres type mapping
# ---------------------------------------------------------------------------

DUCKDB_TYPE_MAP: dict[str, str] = {
    "VARCHAR": "text",
    "BIGINT": "numeric",
    "INTEGER": "integer",
    "SMALLINT": "integer",
    "TINYINT": "integer",
    "HUGEINT": "numeric",
    "DOUBLE": "numeric",
    "FLOAT": "numeric",
    "DECIMAL": "numeric",
    "BOOLEAN": "boolean",
    "DATE": "date",
    "TIMESTAMP": "timestamp",
    "TIMESTAMP WITH TIME ZONE": "timestamptz",
    "TIME": "time",
    "BLOB": "text",
}


def normalize_column_name(header: str) -> str:
    """Normalize a single CSV header to a clean snake_case identifier.

    Rules applied in order:
    1. Lowercase the input.
    2. Replace any non-alphanumeric character with an underscore.
    3. Collapse consecutive underscores into one.
    4. Strip leading and trailing underscores.
    5. Prefix with ``col_`` if the result starts with a digit or is empty.
    """
    name = header.lower()
    name = re.sub(r"[^a-z0-9]", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")

    if not name or name[0].isdigit():
        name = f"col_{name}"

    return name


def normalize_columns(headers: list[str]) -> list[str]:
    """Normalize a list of CSV headers, deduplicating collisions.

    When two or more headers normalize to the same identifier, the first
    occurrence keeps the base name and subsequent ones receive a ``_2``,
    ``_3``, ... suffix.
    """
    seen: dict[str, int] = {}
    result: list[str] = []

    for header in headers:
        base = normalize_column_name(header)
        count = seen.get(base, 0) + 1
        seen[base] = count

        if count == 1:
            result.append(base)
        else:
            result.append(f"{base}_{count}")

    return result


def map_duckdb_type(duckdb_type: str) -> str:
    """Map a DuckDB type string to a simplified Postgres-friendly type.

    Handles parameterized types like ``DECIMAL(18,3)`` by stripping the
    parameter portion before lookup. Returns ``"text"`` for unknown types.
    """
    base_type = duckdb_type.split("(")[0].strip().upper()
    return DUCKDB_TYPE_MAP.get(base_type, "text")
