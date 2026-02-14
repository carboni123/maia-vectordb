"""Unit tests for the vector store service layer.

Tests call the async service functions directly with a mock AsyncSession,
verifying ORM interactions (add, commit, refresh, execute, delete) and
error handling (NotFoundError).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from maia_vectordb.core.exceptions import NotFoundError
from maia_vectordb.models.vector_store import VectorStore
from maia_vectordb.services.vector_store_service import (
    create_vector_store,
    delete_vector_store,
    get_vector_store,
    list_vector_stores,
)
from tests.conftest import make_store

# ---------------------------------------------------------------------------
# create_vector_store
# ---------------------------------------------------------------------------


class TestCreateVectorStore:
    """Tests for create_vector_store service function."""

    async def test_create_adds_store_to_session(
        self, mock_session: MagicMock
    ) -> None:
        mock_session.refresh = AsyncMock()

        await create_vector_store(mock_session, name="new-store")

        mock_session.add.assert_called_once()
        added_obj = mock_session.add.call_args[0][0]
        assert isinstance(added_obj, VectorStore)
        assert added_obj.name == "new-store"

    async def test_create_commits_session(self, mock_session: MagicMock) -> None:
        mock_session.refresh = AsyncMock()

        await create_vector_store(mock_session, name="s")

        mock_session.commit.assert_awaited_once()

    async def test_create_refreshes_after_commit(
        self, mock_session: MagicMock
    ) -> None:
        mock_session.refresh = AsyncMock()

        store = await create_vector_store(mock_session, name="s")

        mock_session.refresh.assert_awaited_once_with(store)

    async def test_create_returns_orm_object(
        self, mock_session: MagicMock
    ) -> None:
        mock_session.refresh = AsyncMock()

        result = await create_vector_store(mock_session, name="my-store")

        assert isinstance(result, VectorStore)
        assert result.name == "my-store"

    async def test_create_with_metadata(self, mock_session: MagicMock) -> None:
        mock_session.refresh = AsyncMock()
        meta: dict[str, object] = {"env": "production", "version": "2"}

        result = await create_vector_store(
            mock_session, name="meta-store", metadata=meta
        )

        assert result.metadata_ == meta

    async def test_create_without_metadata_defaults_none(
        self, mock_session: MagicMock
    ) -> None:
        mock_session.refresh = AsyncMock()

        result = await create_vector_store(mock_session, name="plain")

        assert result.metadata_ is None


# ---------------------------------------------------------------------------
# list_vector_stores
# ---------------------------------------------------------------------------


class TestListVectorStores:
    """Tests for list_vector_stores service function."""

    def _mock_execute(
        self, session: MagicMock, rows: list[MagicMock]
    ) -> None:
        """Set up mock_session.execute to return *rows* via scalars().all()."""
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        session.execute = AsyncMock(return_value=result)

    async def test_empty_list(self, mock_session: MagicMock) -> None:
        self._mock_execute(mock_session, [])

        stores, has_more = await list_vector_stores(
            mock_session, limit=20, offset=0, order="desc"
        )

        assert stores == []
        assert has_more is False

    async def test_populated_list(self, mock_session: MagicMock) -> None:
        rows = [make_store(name=f"s-{i}") for i in range(3)]
        self._mock_execute(mock_session, rows)

        stores, has_more = await list_vector_stores(
            mock_session, limit=20, offset=0, order="desc"
        )

        assert len(stores) == 3
        assert has_more is False

    async def test_has_more_when_extra_row(
        self, mock_session: MagicMock
    ) -> None:
        # Return limit+1 rows to trigger has_more=True
        rows = [make_store(name=f"s-{i}") for i in range(3)]
        self._mock_execute(mock_session, rows)

        stores, has_more = await list_vector_stores(
            mock_session, limit=2, offset=0, order="desc"
        )

        assert len(stores) == 2
        assert has_more is True

    async def test_offset_forwarded(self, mock_session: MagicMock) -> None:
        self._mock_execute(mock_session, [])

        await list_vector_stores(
            mock_session, limit=10, offset=5, order="asc"
        )

        mock_session.execute.assert_awaited_once()

    async def test_asc_order(self, mock_session: MagicMock) -> None:
        rows = [make_store(name="a")]
        self._mock_execute(mock_session, rows)

        stores, _ = await list_vector_stores(
            mock_session, limit=20, offset=0, order="asc"
        )

        assert len(stores) == 1
        mock_session.execute.assert_awaited_once()

    async def test_desc_order(self, mock_session: MagicMock) -> None:
        rows = [make_store(name="z")]
        self._mock_execute(mock_session, rows)

        stores, _ = await list_vector_stores(
            mock_session, limit=20, offset=0, order="desc"
        )

        assert len(stores) == 1
        mock_session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_vector_store
# ---------------------------------------------------------------------------


class TestGetVectorStore:
    """Tests for get_vector_store service function."""

    async def test_found_returns_store(self, mock_session: MagicMock) -> None:
        store = make_store(name="found")
        mock_session.get = AsyncMock(return_value=store)

        result = await get_vector_store(mock_session, store.id)

        assert result is store
        mock_session.get.assert_awaited_once_with(VectorStore, store.id)

    async def test_not_found_raises(self, mock_session: MagicMock) -> None:
        mock_session.get = AsyncMock(return_value=None)
        missing_id = uuid.uuid4()

        with pytest.raises(NotFoundError, match="Vector store not found"):
            await get_vector_store(mock_session, missing_id)


# ---------------------------------------------------------------------------
# delete_vector_store
# ---------------------------------------------------------------------------


class TestDeleteVectorStore:
    """Tests for delete_vector_store service function."""

    async def test_found_deletes_and_commits(
        self, mock_session: MagicMock
    ) -> None:
        store = make_store(name="doomed")
        mock_session.get = AsyncMock(return_value=store)

        result = await delete_vector_store(mock_session, store.id)

        mock_session.delete.assert_awaited_once_with(store)
        mock_session.commit.assert_awaited_once()
        assert result == str(store.id)

    async def test_found_returns_id_string(
        self, mock_session: MagicMock
    ) -> None:
        store = make_store(name="to-remove")
        mock_session.get = AsyncMock(return_value=store)

        result = await delete_vector_store(mock_session, store.id)

        assert isinstance(result, str)
        assert result == str(store.id)

    async def test_not_found_raises(self, mock_session: MagicMock) -> None:
        mock_session.get = AsyncMock(return_value=None)
        missing_id = uuid.uuid4()

        with pytest.raises(NotFoundError, match="Vector store not found"):
            await delete_vector_store(mock_session, missing_id)

    async def test_delete_calls_get_with_correct_args(
        self, mock_session: MagicMock
    ) -> None:
        store = make_store()
        mock_session.get = AsyncMock(return_value=store)

        await delete_vector_store(mock_session, store.id)

        mock_session.get.assert_awaited_once_with(VectorStore, store.id)
