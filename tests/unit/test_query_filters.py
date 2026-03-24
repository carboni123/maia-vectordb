"""Tests for the metadata filter SQL builder (query_filters.py).

This module is the SQL injection defense for metadata filters, so
thorough testing of alias validation, parameterization, and edge
cases is critical.
"""

from __future__ import annotations

import pytest

from maia_vectordb.services.query_filters import build_metadata_clauses


class TestBuildMetadataClauses:
    """Tests for build_metadata_clauses."""

    # ----- Empty / None filter -------------------------------------------------

    def test_none_filter_returns_empty(self) -> None:
        clauses, params = build_metadata_clauses(None)
        assert clauses == []
        assert params == {}

    def test_empty_dict_returns_empty(self) -> None:
        clauses, params = build_metadata_clauses({})
        assert clauses == []
        assert params == {}

    # ----- Single key-value filter ---------------------------------------------

    def test_single_filter(self) -> None:
        clauses, params = build_metadata_clauses({"author": "Alice"})
        assert len(clauses) == 1
        assert clauses[0] == "fc.metadata->>:filter_key_0 = :filter_val_0"
        assert params == {"filter_key_0": "author", "filter_val_0": "Alice"}

    # ----- Multiple key-value filters ------------------------------------------

    def test_multiple_filters(self) -> None:
        clauses, params = build_metadata_clauses(
            {"author": "Alice", "category": "science"}
        )
        assert len(clauses) == 2
        assert "fc.metadata->>:filter_key_0 = :filter_val_0" in clauses
        assert "fc.metadata->>:filter_key_1 = :filter_val_1" in clauses
        assert params["filter_key_0"] == "author"
        assert params["filter_val_0"] == "Alice"
        assert params["filter_key_1"] == "category"
        assert params["filter_val_1"] == "science"

    # ----- Value type coercion -------------------------------------------------

    def test_integer_value_converted_to_string(self) -> None:
        _, params = build_metadata_clauses({"count": 42})
        assert params["filter_val_0"] == "42"

    def test_boolean_value_converted_to_string(self) -> None:
        _, params = build_metadata_clauses({"active": True})
        assert params["filter_val_0"] == "True"

    def test_none_value_converted_to_string(self) -> None:
        _, params = build_metadata_clauses({"tag": None})
        assert params["filter_val_0"] == "None"

    # ----- Special characters in keys and values --------------------------------

    def test_key_with_special_characters(self) -> None:
        """Keys with SQL-significant chars are bind params, not interpolated."""
        clauses, params = build_metadata_clauses({"a'; DROP TABLE--": "val"})
        assert len(clauses) == 1
        # Key goes as a bind parameter, never in the SQL string
        assert params["filter_key_0"] == "a'; DROP TABLE--"

    def test_value_with_special_characters(self) -> None:
        """Values with SQL-significant chars are bind params, not interpolated."""
        _, params = build_metadata_clauses({"key": "val'; DROP TABLE--"})
        assert params["filter_val_0"] == "val'; DROP TABLE--"

    def test_key_with_jsonb_operators(self) -> None:
        """Keys containing JSONB operators are safely parameterized."""
        _, params = build_metadata_clauses({"->>'payload'": "x"})
        assert params["filter_key_0"] == "->>'payload'"

    # ----- Custom alias --------------------------------------------------------

    def test_custom_alias(self) -> None:
        clauses, _ = build_metadata_clauses({"k": "v"}, alias="fc_inner")
        assert clauses[0] == "fc_inner.metadata->>:filter_key_0 = :filter_val_0"

    def test_underscore_alias(self) -> None:
        clauses, _ = build_metadata_clauses({"k": "v"}, alias="t_")
        assert clauses[0].startswith("t_.")

    # ----- Alias validation (SQL injection defense) ----------------------------

    def test_alias_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError, match="Invalid table alias"):
            build_metadata_clauses({"k": "v"}, alias="FC")

    def test_alias_rejects_digits(self) -> None:
        with pytest.raises(ValueError, match="Invalid table alias"):
            build_metadata_clauses({"k": "v"}, alias="fc1")

    def test_alias_rejects_special_characters(self) -> None:
        with pytest.raises(ValueError, match="Invalid table alias"):
            build_metadata_clauses({"k": "v"}, alias="fc;--")

    def test_alias_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="Invalid table alias"):
            build_metadata_clauses({"k": "v"}, alias="")

    def test_alias_rejects_spaces(self) -> None:
        with pytest.raises(ValueError, match="Invalid table alias"):
            build_metadata_clauses({"k": "v"}, alias="fc inner")

    def test_alias_rejects_sql_injection_attempt(self) -> None:
        with pytest.raises(ValueError, match="Invalid table alias"):
            build_metadata_clauses({"k": "v"}, alias="fc; DROP TABLE users--")

    # ----- Parameterization correctness ----------------------------------------

    def test_params_are_numbered_sequentially(self) -> None:
        """Verify bind param names are deterministic and sequential."""
        clauses, params = build_metadata_clauses({"a": "1", "b": "2", "c": "3"})
        assert len(clauses) == 3
        for i in range(3):
            assert f"filter_key_{i}" in params
            assert f"filter_val_{i}" in params

    def test_no_raw_user_data_in_clauses(self) -> None:
        """Verify that user-supplied keys/values never appear in clause strings."""
        user_key = "dangerous_key"
        user_val = "dangerous_val"
        clauses, _ = build_metadata_clauses({user_key: user_val})
        for clause in clauses:
            assert user_key not in clause
            assert user_val not in clause
