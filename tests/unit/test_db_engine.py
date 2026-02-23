"""Tests for database engine configuration and startup DDL."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.pool import AsyncAdaptedQueuePool

from maia_vectordb.db.base import Base
from maia_vectordb.db.engine import (
    _create_engine,
    dispose_engine,
    get_db_session,
    init_engine,
)


class TestConnectionPooling:
    """AC4: Connection pooling configured."""

    def test_engine_uses_queue_pool(self) -> None:
        """Engine should use QueuePool (the default with pool args)."""
        engine = _create_engine()
        pool = engine.pool
        assert isinstance(pool, AsyncAdaptedQueuePool)
        pool.dispose()

    def test_pool_size_configured(self) -> None:
        """Pool size should be set to 5."""
        engine = _create_engine()
        pool = engine.pool
        assert isinstance(pool, AsyncAdaptedQueuePool)
        assert pool.size() == 5
        pool.dispose()

    def test_max_overflow_configured(self) -> None:
        """Max overflow should be set to 10."""
        engine = _create_engine()
        pool = engine.pool
        assert isinstance(pool, AsyncAdaptedQueuePool)
        assert pool._max_overflow == 10
        pool.dispose()

    def test_pool_pre_ping_enabled(self) -> None:
        """Pool pre-ping enabled for connection health checks."""
        engine = _create_engine()
        pool = engine.pool
        assert isinstance(pool, AsyncAdaptedQueuePool)
        assert pool._pre_ping is True
        pool.dispose()

    def test_pool_recycle_configured(self) -> None:
        """Pool recycle should be set to 300 seconds."""
        engine = _create_engine()
        pool = engine.pool
        assert isinstance(pool, AsyncAdaptedQueuePool)
        assert pool._recycle == 300
        pool.dispose()


class TestStartupDDL:
    """AC1: Tables created on startup with pgvector extension enabled."""

    @pytest.mark.asyncio
    async def test_init_engine_enables_pgvector_extension(self) -> None:
        """init_engine executes CREATE EXTENSION IF NOT EXISTS vector."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_conn.run_sync = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.begin = MagicMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(
            return_value=mock_conn,
        )
        mock_engine.begin.return_value.__aexit__ = AsyncMock(
            return_value=None,
        )
        mock_engine.dispose = AsyncMock()

        with patch(
            "maia_vectordb.db.engine._create_engine",
            return_value=mock_engine,
        ):
            await init_engine()

        # Verify pgvector extension creation was called
        execute_calls = mock_conn.execute.call_args_list
        assert len(execute_calls) >= 1
        sql_text = str(execute_calls[0][0][0])
        assert "CREATE EXTENSION IF NOT EXISTS vector" in sql_text

        # Clean up module-level state
        await dispose_engine()

    @pytest.mark.asyncio
    async def test_init_engine_calls_create_all(self) -> None:
        """init_engine calls Base.metadata.create_all for DDL."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_conn.run_sync = AsyncMock()

        mock_engine = MagicMock()
        mock_engine.begin = MagicMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(
            return_value=mock_conn,
        )
        mock_engine.begin.return_value.__aexit__ = AsyncMock(
            return_value=None,
        )
        mock_engine.dispose = AsyncMock()

        with patch(
            "maia_vectordb.db.engine._create_engine",
            return_value=mock_engine,
        ):
            await init_engine()

        # Verify create_all was called via run_sync
        mock_conn.run_sync.assert_called_once_with(
            Base.metadata.create_all,
        )

        # Clean up module-level state
        await dispose_engine()


class TestSessionFactory:
    """Session factory and dependency injection tests."""

    @pytest.mark.asyncio
    async def test_get_db_session_raises_without_init(self) -> None:
        """get_db_session raises RuntimeError if engine not initialised."""
        # Ensure engine is not initialised
        await dispose_engine()

        with pytest.raises(RuntimeError, match="Database engine not initialised"):
            async for _session in get_db_session():
                pass  # pragma: no cover


class TestAllTablesRegistered:
    """Verify all model tables are registered on Base.metadata."""

    def test_vector_stores_table_in_metadata(self) -> None:
        # Import models to ensure they're registered
        import maia_vectordb.models  # noqa: F401

        assert "vector_stores" in Base.metadata.tables

    def test_files_table_in_metadata(self) -> None:
        import maia_vectordb.models  # noqa: F401

        assert "files" in Base.metadata.tables

    def test_file_chunks_table_in_metadata(self) -> None:
        import maia_vectordb.models  # noqa: F401

        assert "file_chunks" in Base.metadata.tables
