"""Tests for JSON serialization helpers (json_utils.py)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from maia_vectordb.services.json_utils import to_json_safe


class TestToJsonSafe:
    """Tests for to_json_safe type conversion."""

    # ----- None ----------------------------------------------------------------

    def test_none_returns_none(self) -> None:
        assert to_json_safe(None) is None

    # ----- Decimal -------------------------------------------------------------

    def test_decimal_integer_returns_int(self) -> None:
        assert to_json_safe(Decimal("42")) == 42
        assert isinstance(to_json_safe(Decimal("42")), int)

    def test_decimal_zero_returns_int(self) -> None:
        assert to_json_safe(Decimal("0")) == 0
        assert isinstance(to_json_safe(Decimal("0")), int)

    def test_decimal_negative_integer_returns_int(self) -> None:
        assert to_json_safe(Decimal("-7")) == -7
        assert isinstance(to_json_safe(Decimal("-7")), int)

    def test_decimal_float_returns_float(self) -> None:
        result = to_json_safe(Decimal("3.14"))
        assert result == 3.14
        assert isinstance(result, float)

    def test_decimal_trailing_zeros_returns_int(self) -> None:
        """Decimal('42.00') is integral and should return int."""
        assert to_json_safe(Decimal("42.00")) == 42
        assert isinstance(to_json_safe(Decimal("42.00")), int)

    # ----- datetime ------------------------------------------------------------

    def test_datetime_returns_isoformat(self) -> None:
        dt = datetime(2026, 3, 10, 14, 30, 0, tzinfo=timezone.utc)
        assert to_json_safe(dt) == "2026-03-10T14:30:00+00:00"

    def test_naive_datetime_returns_isoformat(self) -> None:
        dt = datetime(2026, 1, 1, 0, 0, 0)
        assert to_json_safe(dt) == "2026-01-01T00:00:00"

    # ----- date ----------------------------------------------------------------

    def test_date_returns_isoformat(self) -> None:
        d = date(2026, 3, 10)
        assert to_json_safe(d) == "2026-03-10"

    # ----- time ----------------------------------------------------------------

    def test_time_returns_isoformat(self) -> None:
        t = time(14, 30, 0)
        assert to_json_safe(t) == "14:30:00"

    # ----- UUID ----------------------------------------------------------------

    def test_uuid_returns_string(self) -> None:
        u = uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert to_json_safe(u) == "12345678-1234-5678-1234-567812345678"
        assert isinstance(to_json_safe(u), str)

    # ----- bytes ---------------------------------------------------------------

    def test_bytes_utf8_returns_string(self) -> None:
        assert to_json_safe(b"hello") == "hello"

    def test_bytes_invalid_utf8_uses_replacement(self) -> None:
        """Invalid UTF-8 bytes use the replacement character."""
        result = to_json_safe(b"\xff\xfe")
        assert "\ufffd" in result  # replacement character

    def test_empty_bytes_returns_empty_string(self) -> None:
        assert to_json_safe(b"") == ""

    # ----- Passthrough types ---------------------------------------------------

    def test_string_passthrough(self) -> None:
        assert to_json_safe("hello") == "hello"

    def test_int_passthrough(self) -> None:
        assert to_json_safe(42) == 42

    def test_float_passthrough(self) -> None:
        assert to_json_safe(3.14) == 3.14

    def test_bool_passthrough(self) -> None:
        assert to_json_safe(True) is True

    def test_list_passthrough(self) -> None:
        val = [1, 2, 3]
        assert to_json_safe(val) is val

    def test_dict_passthrough(self) -> None:
        val = {"key": "value"}
        assert to_json_safe(val) is val
