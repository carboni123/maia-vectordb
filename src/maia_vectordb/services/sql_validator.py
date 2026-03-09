"""SQL validation and preparation for structured CSV queries.

Ensures user-provided SQL is safe to execute: SELECT-only, references only
the csv_rows table, and auto-limits result sets.
"""

from __future__ import annotations

import re

import sqlparse


class SQLValidationError(Exception):
    """Raised when SQL fails safety validation."""


# Keywords that must never appear as standalone words in the query.
_DANGEROUS_KEYWORDS = frozenset(
    [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "COPY",
    ]
)

# Matches table references after FROM or JOIN (with optional schema qualifier).
_TABLE_REF_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
    re.IGNORECASE,
)

# Matches the csv_rows identifier as a whole word.
_CSV_ROWS_RE = re.compile(r"\bcsv_rows\b", re.IGNORECASE)


def validate_and_prepare_sql(sql: str, schema_name: str) -> str:
    """Validate user SQL for safety and prepare it for execution.

    Validation:
        - Must be a single SELECT statement.
        - Must not contain dangerous DML/DDL keywords.
        - Must only reference the ``csv_rows`` table.
        - Must not use explicit cross-schema references (e.g. ``public.users``).

    Preparation:
        - Schema-qualifies ``csv_rows`` → ``"{schema_name}".csv_rows``.
        - Auto-injects ``LIMIT 5000`` when no LIMIT clause is present.

    Args:
        sql: The raw SQL string from the user / LLM.
        schema_name: The per-vector-store Postgres schema to qualify against.

    Returns:
        The validated and prepared SQL string, ready for execution.

    Raises:
        SQLValidationError: If the SQL fails any safety check.
    """
    # ------------------------------------------------------------------
    # 1. Basic cleanup
    # ------------------------------------------------------------------
    sql = sql.strip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()

    if not sql:
        raise SQLValidationError("SQL query must not be empty.")

    # ------------------------------------------------------------------
    # 2. Parse and enforce single SELECT statement
    # ------------------------------------------------------------------
    statements = [
        s for s in sqlparse.parse(sql) if s.ttype is not sqlparse.tokens.Whitespace
    ]
    # Filter out empty / whitespace-only statements that sqlparse may emit.
    statements = [s for s in statements if s.value.strip()]

    if len(statements) != 1:
        raise SQLValidationError(
            "Only a single SQL statement is allowed."
        )

    stmt = statements[0]
    if stmt.get_type() != "SELECT":
        raise SQLValidationError(
            f"Only SELECT statements are allowed, got: {stmt.get_type()}"
        )

    # ------------------------------------------------------------------
    # 3. Scan for dangerous keywords (whole-word match)
    # ------------------------------------------------------------------
    sql_upper = sql.upper()
    for kw in _DANGEROUS_KEYWORDS:
        if re.search(rf"\b{kw}\b", sql_upper):
            raise SQLValidationError(
                f"Forbidden keyword detected: {kw}"
            )

    # ------------------------------------------------------------------
    # 4. Validate table references
    # ------------------------------------------------------------------
    table_refs = _TABLE_REF_RE.findall(sql)

    for schema_part, table_part in table_refs:
        table_name = table_part.lower()

        # Reject explicit cross-schema references.
        if schema_part and table_name != "csv_rows":
            raise SQLValidationError(
                f"Cross-schema reference not allowed: {schema_part}.{table_part}"
            )

        # Only csv_rows is permitted.
        if table_name != "csv_rows":
            raise SQLValidationError(
                f"Only the csv_rows table may be queried, found: {table_part}"
            )

    # csv_rows must actually be referenced.
    if not _CSV_ROWS_RE.search(sql):
        raise SQLValidationError(
            "Query must reference the csv_rows table."
        )

    # ------------------------------------------------------------------
    # 5. Preparation: schema-qualify csv_rows
    # ------------------------------------------------------------------
    prepared = _CSV_ROWS_RE.sub(f'"{schema_name}".csv_rows', sql)

    # ------------------------------------------------------------------
    # 6. Auto-inject LIMIT if missing
    # ------------------------------------------------------------------
    if not re.search(r"\bLIMIT\b", prepared, re.IGNORECASE):
        prepared = f"{prepared} LIMIT 5000"

    return prepared
