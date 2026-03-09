"""Tests for the SQL validation and preparation service."""

from __future__ import annotations

import pytest

from maia_vectordb.services.sql_validator import (
    SQLValidationError,
    validate_and_prepare_sql,
)


class TestValidateAndPrepareSql:
    def test_accepts_simple_select(self):
        sql = "SELECT data->>'name' FROM csv_rows WHERE file_id = 'abc'"
        result = validate_and_prepare_sql(sql, "vs_test_schema")
        assert "vs_test_schema" in result
        assert "LIMIT" in result.upper()

    def test_rejects_insert(self):
        with pytest.raises(SQLValidationError):
            validate_and_prepare_sql(
                "INSERT INTO csv_rows VALUES ('a', 1, '{}')", "vs_test_schema"
            )

    def test_rejects_drop(self):
        with pytest.raises(SQLValidationError):
            validate_and_prepare_sql("DROP TABLE csv_rows", "vs_test_schema")

    def test_rejects_delete(self):
        with pytest.raises(SQLValidationError):
            validate_and_prepare_sql(
                "DELETE FROM csv_rows WHERE 1=1", "vs_test_schema"
            )

    def test_rejects_update(self):
        with pytest.raises(SQLValidationError):
            validate_and_prepare_sql(
                "UPDATE csv_rows SET data = '{}'", "vs_test_schema"
            )

    def test_rejects_multiple_statements(self):
        with pytest.raises(SQLValidationError, match="single"):
            validate_and_prepare_sql(
                "SELECT 1; DROP TABLE csv_rows;", "vs_test_schema"
            )

    def test_auto_injects_limit(self):
        result = validate_and_prepare_sql("SELECT * FROM csv_rows", "vs_test_schema")
        assert "LIMIT 5000" in result

    def test_preserves_existing_limit(self):
        result = validate_and_prepare_sql(
            "SELECT * FROM csv_rows LIMIT 10", "vs_test_schema"
        )
        assert "LIMIT 10" in result
        assert "LIMIT 5000" not in result

    def test_qualifies_csv_rows_table(self):
        result = validate_and_prepare_sql(
            "SELECT * FROM csv_rows WHERE file_id = 'abc'", "vs_test_schema"
        )
        assert '"vs_test_schema".csv_rows' in result

    def test_rejects_other_table_references(self):
        with pytest.raises(SQLValidationError):
            validate_and_prepare_sql("SELECT * FROM users", "vs_test_schema")

    def test_rejects_cross_schema_reference(self):
        with pytest.raises(SQLValidationError):
            validate_and_prepare_sql(
                "SELECT * FROM public.users", "vs_test_schema"
            )

    def test_rejects_empty_sql(self):
        with pytest.raises(SQLValidationError):
            validate_and_prepare_sql("", "vs_test_schema")

    def test_allows_json_accessors(self):
        # data->>'created_at' should NOT trigger the CREATE keyword check
        sql = "SELECT data->>'created_at' FROM csv_rows"
        result = validate_and_prepare_sql(sql, "vs_test_schema")
        assert '"vs_test_schema".csv_rows' in result

    def test_allows_aggregations(self):
        sql = "SELECT data->>'city', COUNT(*) FROM csv_rows GROUP BY data->>'city'"
        result = validate_and_prepare_sql(sql, "vs_test_schema")
        assert "COUNT" in result

    def test_allows_subquery(self):
        sql = (
            "SELECT * FROM csv_rows WHERE (data->>'price')::numeric > "
            "(SELECT AVG((data->>'price')::numeric) FROM csv_rows)"
        )
        result = validate_and_prepare_sql(sql, "vs_test_schema")
        # Both csv_rows references should be qualified
        assert result.count('"vs_test_schema".csv_rows') == 2
