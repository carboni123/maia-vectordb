"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys


def setup_logging(*, level: int | None = None) -> None:
    """Configure structured logging for the application.

    Log lines include timestamp, level, logger name, and message (which
    middleware enriches with ``request_id`` correlation IDs).

    If *level* is ``None`` (default), reads ``settings.log_level``.
    """
    if level is None:
        from maia_vectordb.core.config import settings

        level = logging.getLevelNamesMapping().get(
            settings.log_level.upper(), logging.INFO
        )

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers on repeated calls (e.g. tests)
    if not root.handlers:
        root.addHandler(handler)
