"""Tests for database engine configuration and startup DDL."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.pool import AsyncAdaptedQueuePool

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


def _make_mock_engine(table_names: list[str] | None = None):
    """Build a mock async engine for init_engine tests.

    ``table_names`` controls what the pg_tables query returns.  When None,
    all required tables are reported as present (happy path).
    """
    if table_names is None:
        table_names = ["vector_stores", "files", "file_chunks"]

    # Build a mock result whose .fetchall() returns synchronous rows
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [(t,) for t in table_names]

    call_count = 0
    original_execute = AsyncMock()

    async def _execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            # Second call is the pg_tables query
            return mock_result
        return original_execute.return_value

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(side_effect=_execute_side_effect)
    mock_conn.run_sync = AsyncMock()

    mock_engine = MagicMock()
    mock_engine.begin = MagicMock()
    mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_engine.dispose = AsyncMock()

    return mock_engine, mock_conn


class TestStartupDDL:
    """AC1: pgvector extension enabled and schema verified on startup."""

    @pytest.mark.asyncio
    async def test_init_engine_enables_pgvector_extension(self) -> None:
        """init_engine executes CREATE EXTENSION IF NOT EXISTS vector."""
        mock_engine, mock_conn = _make_mock_engine()

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

        await dispose_engine()

    @pytest.mark.asyncio
    async def test_init_engine_skips_create_all_when_tables_exist(self) -> None:
        """When all required tables exist, create_all is NOT called."""
        mock_engine, mock_conn = _make_mock_engine(
            table_names=["vector_stores", "files", "file_chunks"],
        )

        with patch(
            "maia_vectordb.db.engine._create_engine",
            return_value=mock_engine,
        ):
            await init_engine()

        # create_all should NOT have been called (tables already exist)
        mock_conn.run_sync.assert_not_called()

        await dispose_engine()

    @pytest.mark.asyncio
    async def test_init_engine_falls_back_to_create_all_when_tables_missing(self) -> None:
        """When tables are missing, init_engine falls back to create_all."""
        mock_engine, mock_conn = _make_mock_engine(
            table_names=[],  # No tables exist
        )

        with patch(
            "maia_vectordb.db.engine._create_engine",
            return_value=mock_engine,
        ):
            await init_engine()

        # create_all should have been called as fallback
        mock_conn.run_sync.assert_called_once()

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
        import maia_vectordb.models  # noqa: F401
        from maia_vectordb.db.base import Base

        assert "vector_stores" in Base.metadata.tables

    def test_files_table_in_metadata(self) -> None:
        import maia_vectordb.models  # noqa: F401
        from maia_vectordb.db.base import Base

        assert "files" in Base.metadata.tables

    def test_file_chunks_table_in_metadata(self) -> None:
        import maia_vectordb.models  # noqa: F401
        from maia_vectordb.db.base import Base

        assert "file_chunks" in Base.metadata.tables
