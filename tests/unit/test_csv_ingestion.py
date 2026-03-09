"""Tests for CSV structured ingestion — DuckDB parsing and metadata building."""

from __future__ import annotations

from maia_vectordb.services.csv_ingestion import (
    build_structured_metadata,
    parse_csv_with_duckdb,
)

# ---------------------------------------------------------------------------
# parse_csv_with_duckdb
# ---------------------------------------------------------------------------


class TestParseCsvWithDuckdb:
    """DuckDB-based CSV parsing with type inference and normalization."""

    def test_parses_simple_csv(self) -> None:
        csv = "Name,Age,City\nAlice,30,Austin\nBob,25,Dallas"
        columns, rows = parse_csv_with_duckdb(csv)

        assert len(columns) == 3
        assert len(rows) == 2

        # Normalized column names
        col_names = [c["normalized"] for c in columns]
        assert col_names == ["name", "age", "city"]

        # Original headers preserved
        assert columns[0]["original_header"] == "Name"
        assert columns[1]["original_header"] == "Age"
        assert columns[2]["original_header"] == "City"

        # Types inferred
        assert columns[1]["inferred_type"] in ("integer", "numeric")
        assert columns[2]["inferred_type"] == "text"

        # Row values
        assert rows[0]["name"] == "Alice"
        assert rows[0]["age"] in (30, 30.0)
        assert rows[1]["city"] == "Dallas"

    def test_normalizes_messy_headers(self) -> None:
        csv = "Price (USD),# Beds,City Name\n500000,3,Austin"
        columns, rows = parse_csv_with_duckdb(csv)

        assert columns[0]["normalized"] == "price_usd"
        assert columns[0]["original_header"] == "Price (USD)"
        assert columns[1]["normalized"] == "beds"
        assert columns[2]["normalized"] == "city_name"

        assert len(rows) == 1
        assert rows[0]["price_usd"] in (500000, 500000.0)

    def test_handles_empty_csv(self) -> None:
        csv = "Name,Age,City"
        columns, rows = parse_csv_with_duckdb(csv)

        assert len(columns) == 3
        assert rows == []
        # No sample_values when there are no rows
        for col in columns:
            assert "sample_values" not in col

    def test_includes_sample_values(self) -> None:
        lines = ["Value"]
        for i in range(1, 8):
            lines.append(str(i * 10))
        csv = "\n".join(lines)

        columns, rows = parse_csv_with_duckdb(csv)

        assert len(rows) == 7
        assert "sample_values" in columns[0]
        # At most 3 sample values
        assert len(columns[0]["sample_values"]) <= 3

    def test_handles_null_values(self) -> None:
        csv = "Name,Age\nAlice,\nBob,25"
        columns, rows = parse_csv_with_duckdb(csv)

        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["age"] is None
        assert rows[1]["age"] in (25, 25.0)

    def test_converts_decimal_to_float(self) -> None:
        csv = "Price\n19.99\n29.50"
        columns, rows = parse_csv_with_duckdb(csv)

        # Regardless of whether DuckDB infers DOUBLE or DECIMAL,
        # the values should be JSON-safe (int or float, not Decimal).
        for row in rows:
            assert isinstance(row["price"], (int, float))

    def test_converts_date_to_isoformat(self) -> None:
        csv = "EventDate\n2025-06-15\n2025-12-25"
        columns, rows = parse_csv_with_duckdb(csv)

        # DuckDB may infer DATE type → should be converted to isoformat string
        for row in rows:
            val = row["eventdate"]
            # Could be a string (isoformat) if DuckDB infers DATE,
            # or remain a string if DuckDB treats it as VARCHAR.
            assert isinstance(val, str)
            assert "2025" in val


# ---------------------------------------------------------------------------
# build_structured_metadata
# ---------------------------------------------------------------------------


class TestBuildStructuredMetadata:
    """Metadata dict construction for structured CSV files."""

    def test_builds_metadata_dict(self) -> None:
        columns = [
            {"normalized": "name", "original_header": "Name", "inferred_type": "text"},
            {
                "normalized": "age",
                "original_header": "Age",
                "inferred_type": "integer",
            },
        ]
        result = build_structured_metadata(columns, row_count=42)

        # "structured" is a truthy dict (not a boolean)
        assert result["structured"]
        assert isinstance(result["structured"], dict)
        assert result["structured"]["table_name"] == "csv_rows"
        assert result["structured"]["row_count"] == 42
        assert result["structured"]["columns"] == columns

    def test_zero_rows(self) -> None:
        result = build_structured_metadata([], row_count=0)

        assert result["structured"]
        assert isinstance(result["structured"], dict)
        assert result["structured"]["row_count"] == 0
        assert result["structured"]["columns"] == []
