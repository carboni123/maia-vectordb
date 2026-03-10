"""Shared JSON serialization helpers."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any


def to_json_safe(value: Any) -> Any:
    """Convert a Python/DB value to a JSON-serializable equivalent.

    Handles types commonly returned by DuckDB and PostgreSQL:
    Decimal, datetime, date, time, UUID, and bytes.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
