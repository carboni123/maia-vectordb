"""Tests for application lifespan and startup/shutdown."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestApplicationLifespan:
    """Tests for FastAPI lifespan event handlers."""

    @pytest.mark.asyncio
    @patch("openai.AsyncOpenAI")
    @patch("maia_vectordb.main.get_encoding")
    @patch("maia_vectordb.main.dispose_engine")
    @patch("maia_vectordb.main.init_engine")
    async def test_lifespan_calls_init_and_dispose(
        self,
        mock_init: AsyncMock,
        mock_dispose: AsyncMock,
        mock_encoding: MagicMock,
        mock_openai_cls: MagicMock,
    ) -> None:
        """Lifespan context manager calls init_engine and dispose_engine."""
        from maia_vectordb.main import lifespan

        # Make the OpenAI client mock return an awaitable for embeddings.create
        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock()
        mock_openai_cls.return_value = mock_client

        mock_app = MagicMock()

        async with lifespan(mock_app):
            mock_init.assert_called_once()
            mock_dispose.assert_not_called()
            mock_encoding.assert_called_once()

        mock_dispose.assert_called_once()

    @pytest.mark.asyncio
    @patch("openai.AsyncOpenAI")
    @patch("maia_vectordb.main.get_encoding")
    @patch("maia_vectordb.main.dispose_engine")
    @patch("maia_vectordb.main.init_engine")
    async def test_lifespan_continues_if_openai_warmup_fails(
        self,
        mock_init: AsyncMock,
        mock_dispose: AsyncMock,
        mock_encoding: MagicMock,
        mock_openai_cls: MagicMock,
    ) -> None:
        """Startup should succeed even if OpenAI warmup fails."""
        from maia_vectordb.main import lifespan

        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(
            side_effect=Exception("OpenAI unreachable"),
        )
        mock_openai_cls.return_value = mock_client

        mock_app = MagicMock()

        # Should not raise despite OpenAI failure
        async with lifespan(mock_app):
            mock_init.assert_called_once()

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
