"""Tests for CSV column normalization and DuckDB type mapping utilities."""

from __future__ import annotations

from maia_vectordb.services.csv_utils import (
    map_duckdb_type,
    normalize_column_name,
    normalize_columns,
)

# ---------------------------------------------------------------------------
# normalize_column_name
# ---------------------------------------------------------------------------


class TestNormalizeColumnName:
    """Single header normalization to snake_case identifiers."""

    def test_simple_lowercase(self) -> None:
        assert normalize_column_name("Price") == "price"

    def test_spaces_to_underscores(self) -> None:
        assert normalize_column_name("First Name") == "first_name"

    def test_special_chars_removed(self) -> None:
        assert normalize_column_name("Price (USD)") == "price_usd"

    def test_hash_and_symbols(self) -> None:
        assert normalize_column_name("# of Beds") == "of_beds"

    def test_leading_digit_prefix(self) -> None:
        assert normalize_column_name("123column") == "col_123column"

    def test_empty_string(self) -> None:
        assert normalize_column_name("") == "col_"

    def test_all_symbols(self) -> None:
        assert normalize_column_name("###") == "col_"

    def test_consecutive_separators_collapsed(self) -> None:
        assert normalize_column_name("city   name") == "city_name"

    def test_trailing_underscores_stripped(self) -> None:
        assert normalize_column_name("value_") == "value"


# ---------------------------------------------------------------------------
# normalize_columns
# ---------------------------------------------------------------------------


class TestNormalizeColumns:
    """Batch header normalization with deduplication."""

    def test_deduplicates_collisions(self) -> None:
        result = normalize_columns(["Name", "name", "NAME"])
        assert result == ["name", "name_2", "name_3"]

    def test_preserves_unique(self) -> None:
        result = normalize_columns(["Price", "Beds", "City"])
        assert result == ["price", "beds", "city"]

    def test_empty_list(self) -> None:
        assert normalize_columns([]) == []


# ---------------------------------------------------------------------------
# map_duckdb_type
# ---------------------------------------------------------------------------


class TestMapDuckdbType:
    """DuckDB type string to simplified Postgres type mapping."""

    def test_varchar_to_text(self) -> None:
        assert map_duckdb_type("VARCHAR") == "text"

    def test_bigint_to_numeric(self) -> None:
        assert map_duckdb_type("BIGINT") == "numeric"

    def test_integer_to_integer(self) -> None:
        assert map_duckdb_type("INTEGER") == "integer"

    def test_parameterized_decimal(self) -> None:
        assert map_duckdb_type("DECIMAL(18,3)") == "numeric"

    def test_unknown_type_defaults_to_text(self) -> None:
        assert map_duckdb_type("UNKNOWN_TYPE") == "text"
