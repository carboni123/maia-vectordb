"""Shared SQL filter building for search queries.

All functions return parameterized SQL clause templates with ``:param``
bind-parameter placeholders — never raw user data. This centralizes
the metadata filter pattern so that user-supplied values are always
separated from SQL structure.
"""

from __future__ import annotations

from typing import Any

# Valid table alias characters (prevent injection via alias)
_ALIAS_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz_")


def build_metadata_clauses(
    metadata_filter: dict[str, Any] | None,
    *,
    alias: str = "fc",
) -> tuple[list[str], dict[str, Any]]:
    """Build WHERE clauses for metadata key-value filters.

    Each (key, value) pair becomes a JSONB extraction check using
    bind parameters for both the key and the value, so no user data
    is ever interpolated into the SQL string.

    Parameters
    ----------
    metadata_filter:
        Optional dict of metadata key→value filters.
    alias:
        Table alias for the ``file_chunks`` table (e.g. ``"fc"`` or
        ``"fc_inner"``). Validated to contain only safe characters.

    Returns
    -------
    tuple[list[str], dict[str, Any]]
        (list of SQL clause strings, dict of bind parameters).
    """
    if not alias or not all(c in _ALIAS_CHARS for c in alias):
        raise ValueError(f"Invalid table alias: {alias!r}")

    clauses: list[str] = []
    params: dict[str, Any] = {}

    if metadata_filter:
        for i, (key, value) in enumerate(metadata_filter.items()):
            pk = f"filter_key_{i}"
            pv = f"filter_val_{i}"
            clauses.append(f"{alias}.metadata->>:{pk} = :{pv}")
            params[pk] = key
            params[pv] = str(value)

    return clauses, params
