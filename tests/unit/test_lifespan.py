"""Tests for application lifespan and startup/shutdown."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestApplicationLifespan:
    """Tests for FastAPI lifespan event handlers."""

    @pytest.mark.asyncio
    @patch("maia_vectordb.main.dispose_engine")
    @patch("maia_vectordb.main.init_engine")
    async def test_lifespan_calls_init_and_dispose(
        self,
        mock_init: AsyncMock,
        mock_dispose: AsyncMock,
    ) -> None:
        """Lifespan context manager calls init_engine and dispose_engine."""
        from unittest.mock import MagicMock

        from maia_vectordb.main import lifespan

        # Mock FastAPI app
        mock_app = MagicMock()

        # Execute lifespan
        async with lifespan(mock_app):
            # During lifespan, init should be called
            mock_init.assert_called_once()
            mock_dispose.assert_not_called()

        # After lifespan exits, dispose should be called
        mock_dispose.assert_called_once()


class TestDatabaseEngineLifecycle:
    """Tests for database engine initialization and disposal."""

    @pytest.mark.asyncio
    async def test_dispose_engine_when_no_engine(self) -> None:
        """dispose_engine() handles case when engine is None."""
        from maia_vectordb.db.engine import dispose_engine

        with patch("maia_vectordb.db.engine._engine", None):
            with patch("maia_vectordb.db.engine._session_factory", None):
                # Should not raise
                await dispose_engine()
