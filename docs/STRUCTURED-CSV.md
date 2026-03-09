# Structured CSV Ingestion

Hybrid CSV ingestion that stores rows as JSONB in Postgres alongside the existing vector embeddings, enabling precise structured queries (filtering, sorting, aggregations) via Text-to-SQL.

## Problem

CSV files uploaded to vector stores are ingested into pgvector for semantic search only. This fails for precise structured queries — filtering, sorting, aggregations, ranges, analytics. A real estate CSV with 100k listings can't reliably answer "3+ bed homes under $600k in Austin, sorted by price" via RAG alone.

## Solution

When a CSV file is uploaded, **also** store its rows as JSONB in a per-vector-store Postgres schema. Two new API endpoints allow querying this structured data via SQL and previewing file contents.

```
CSV Upload
  ├─ Existing: chunks + embeddings (semantic search via /search)
  └─ New: DuckDB parse → JSONB rows in Postgres (structured queries via /query)
```

## Architecture

### Data Flow

```
CSV text
  → DuckDB read_csv_auto (type inference, normalization)
  → Normalized column metadata (stored in files.attributes)
  → JSONB row dicts (batch-inserted into per-VS schema)
  → Available for SQL queries via /query endpoint
```

### Key Design Decisions

**JSONB per-row storage (not one table per CSV).** One fixed `csv_rows` table per vector-store schema. Every CSV row becomes one row with content in a `data JSONB` column. Eliminates dynamic DDL, table explosion, and cleanup complexity.

**DuckDB as parser only.** DuckDB's `read_csv_auto` handles messy CSVs (headers, mixed types, dates, quoting) better than the stdlib csv module. Used only for parsing — no DuckDB storage, no `ATTACH` to Postgres.

**Per-vector-store schema isolation.** Tables stored in `vs_{uuid}` schemas (e.g. `vs_550e8400_e29b_41d4_a716_446655440000`). Created on first CSV upload. Dropped when the vector store is deleted.

**Column normalization to snake_case.** Raw CSV headers are normalized for clean SQL: `"Price (USD)"` → `price_usd`. Duplicates get `_2`, `_3` suffixes. Both normalized and original headers are preserved in metadata.

**Non-fatal ingestion.** The structured CSV path is wrapped in try/except. If it fails, the vector embedding pipeline continues — the file is still searchable via semantic search.

## Database Schema

Each vector store gets its own Postgres schema with a single table:

```sql
CREATE SCHEMA IF NOT EXISTS "vs_{uuid}";

CREATE TABLE IF NOT EXISTS "vs_{uuid}".csv_rows (
    file_id     UUID      NOT NULL,
    row_id      BIGSERIAL NOT NULL,
    data        JSONB     NOT NULL,
    PRIMARY KEY (file_id, row_id)
);

CREATE INDEX idx_csv_rows_file_id ON "vs_{uuid}".csv_rows (file_id);
CREATE INDEX idx_csv_rows_data_gin ON "vs_{uuid}".csv_rows USING GIN (data);
```

The GIN index enables efficient JSONB queries (e.g. `data @> '{"city": "Austin"}'`).

## File Metadata

Column metadata is stored in the file's existing `attributes` JSONB field under the `"structured"` key:

```json
{
  "structured": {
    "table_name": "csv_rows",
    "row_count": 45230,
    "columns": [
      {
        "normalized": "price_usd",
        "original_header": "Price (USD)",
        "inferred_type": "numeric",
        "sample_values": [450000, 620000, 380000]
      },
      {
        "normalized": "beds",
        "original_header": "Beds / Bedrooms",
        "inferred_type": "integer"
      }
    ]
  }
}
```

The `"structured"` key is a dict (truthy) — downstream code uses `attrs.get("structured")` both as a truthiness check and to access `.get("columns")`.

## Source Files

| File | Purpose |
|------|---------|
| `services/csv_utils.py` | Column normalization (`normalize_column_name`, `normalize_columns`) and DuckDB→Postgres type mapping |
| `services/csv_ingestion.py` | Core ingestion: DuckDB parsing, schema creation, row insertion, cleanup |
| `services/sql_validator.py` | SQL safety enforcement: SELECT-only, table whitelist, auto-LIMIT |
| `services/extraction.py` | `is_csv()` helper for CSV detection |
| `services/file_service.py` | Integration point: calls CSV ingestion during file upload/delete |
| `services/vector_store_service.py` | Integration point: drops CSV schema on store deletion |
| `api/structured.py` | Query and preview endpoints |
| `schemas/structured.py` | Pydantic models for query/preview requests and responses |

## SQL Validation

All user-provided SQL is validated before execution:

1. **Single SELECT only** — sqlparse enforces one statement, type must be SELECT
2. **Dangerous keyword scan** — INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT, REVOKE, COPY rejected as whole-word matches
3. **Table whitelist** — only `csv_rows` is permitted. Catches FROM/JOIN references, comma-separated implicit joins, and subquery table references
4. **Cross-schema rejection** — explicit schema qualifiers (e.g. `public.users`, `information_schema.tables`) rejected
5. **Schema qualification** — unqualified `csv_rows` rewritten to `"{schema}".csv_rows`
6. **Auto-LIMIT** — `LIMIT 5000` injected if no LIMIT clause is present
7. **Statement timeout** — `SET LOCAL statement_timeout = '10s'` prevents runaway queries
8. **Response truncation** — results capped at 100 KB

### SQL Query Patterns

Since data is stored as JSONB, queries use the `->>'key'` accessor with casts:

```sql
-- Filter and sort
SELECT data->>'city' AS city, (data->>'price_usd')::numeric AS price
FROM csv_rows
WHERE file_id = 'abc123'
  AND (data->>'beds')::integer >= 3
ORDER BY price
LIMIT 100;

-- Aggregation
SELECT data->>'city', COUNT(*) AS total
FROM csv_rows
WHERE file_id = 'abc123'
GROUP BY data->>'city'
ORDER BY total DESC;

-- Subquery (both must reference csv_rows)
SELECT * FROM csv_rows
WHERE (data->>'price')::numeric > (
  SELECT AVG((data->>'price')::numeric) FROM csv_rows
);
```

## Lifecycle and Cleanup

| Event | Action |
|-------|--------|
| CSV file uploaded | `ensure_csv_schema()` + `insert_csv_rows()` (within caller's transaction) |
| File deleted | `delete_csv_rows_for_file()` removes rows for that file |
| Vector store deleted | `drop_csv_schema()` drops the entire `vs_{uuid}` schema with CASCADE |

All cleanup functions do **not** commit — callers control transaction boundaries.

## Dependencies

| Package | Purpose |
|---------|---------|
| `duckdb` | CSV parsing with `read_csv_auto` |
| `sqlparse` | SQL statement type detection |

Both declared in `pyproject.toml`.

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/unit/test_csv_utils.py` | 17 | Column normalization, deduplication, type mapping |
| `tests/unit/test_csv_ingestion.py` | 9 | DuckDB parsing, metadata building, JSON safety |
| `tests/unit/test_sql_validator.py` | 19 | SELECT enforcement, keyword scan, table whitelist, comma joins, subqueries |
| `tests/unit/test_structured_api.py` | 13 | Query/preview endpoints, error cases, auth |
| `tests/integration/test_structured_csv.py` | 8 | End-to-end with real Postgres |
