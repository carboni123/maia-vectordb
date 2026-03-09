"""Service layer for vector store CRUD operations."""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from maia_vectordb.core.exceptions import NotFoundError
from maia_vectordb.models.file import File, FileStatus
from maia_vectordb.models.vector_store import VectorStore
from maia_vectordb.schemas.vector_store import ExpiresAfter, FileCounts


async def create_vector_store(
    session: AsyncSession,
    name: str,
    metadata: dict[str, object] | None = None,
    expires_after: ExpiresAfter | None = None,
) -> VectorStore:
    """Create a new vector store.

    Parameters
    ----------
    session:
        Database session.
    name:
        Vector store name.
    metadata:
        Optional metadata dictionary.
    expires_after:
        Optional expiration policy. If provided, ``expires_at`` is
        computed as *now + days*.

    Returns
    -------
    VectorStore
        Newly created vector store ORM model.
    """
    store = VectorStore(name=name, metadata_=metadata)
    if expires_after is not None:
        from datetime import datetime, timezone

        store.expires_at = datetime.now(timezone.utc) + timedelta(
            days=expires_after.days,
        )
    session.add(store)
    await session.commit()
    await session.refresh(store)
    return store


async def list_vector_stores(
    session: AsyncSession,
    limit: int,
    offset: int,
    order: str,
) -> tuple[list[VectorStore], bool]:
    """List vector stores with pagination.

    Parameters
    ----------
    session:
        Database session.
    limit:
        Maximum number of stores to return.
    offset:
        Number of stores to skip.
    order:
        Sort order: "asc" or "desc" by created_at.

    Returns
    -------
    tuple[list[VectorStore], bool]
        (list of stores, has_more flag).
    """
    order_col = (
        VectorStore.created_at.asc()
        if order == "asc"
        else VectorStore.created_at.desc()
    )
    stmt = select(VectorStore).order_by(order_col).offset(offset).limit(limit + 1)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    stores = rows[:limit]

    return stores, has_more


async def get_vector_store(
    session: AsyncSession,
    store_id: UUID,
) -> VectorStore:
    """Retrieve a single vector store by ID.

    Parameters
    ----------
    session:
        Database session.
    store_id:
        Vector store UUID.

    Returns
    -------
    VectorStore
        The requested vector store ORM model.

    Raises
    ------
    NotFoundError
        If the vector store does not exist.
    """
    store = await session.get(VectorStore, store_id)
    if store is None:
        raise NotFoundError("Vector store not found")
    return store


async def delete_vector_store(
    session: AsyncSession,
    store_id: UUID,
) -> str:
    """Delete a vector store and all its documents (cascade).

    Parameters
    ----------
    session:
        Database session.
    store_id:
        Vector store UUID.

    Returns
    -------
    str
        ID of the deleted vector store.

    Raises
    ------
    NotFoundError
        If the vector store does not exist.
    """
    store = await session.get(VectorStore, store_id)
    if store is None:
        raise NotFoundError("Vector store not found")
    store_id_str = str(store.id)

    # Clean up structured CSV schema if it exists
    try:
        from maia_vectordb.services.csv_ingestion import drop_csv_schema

        await drop_csv_schema(session, store_id)
    except Exception:
        logger.exception("Failed to drop CSV schema for store %s", store_id)

    await session.delete(store)
    await session.commit()
    return store_id_str


async def get_file_counts(
    session: AsyncSession,
    store_id: UUID,
) -> FileCounts:
    """Compute file processing counts for a vector store.

    Returns a ``FileCounts`` with in_progress, completed, cancelled,
    failed, and total counts computed live from the ``files`` table.
    """
    stmt = (
        select(
            func.count().label("total"),
            func.count()
            .filter(File.status == FileStatus.in_progress)
            .label("in_progress"),
            func.count().filter(File.status == FileStatus.completed).label("completed"),
            func.count().filter(File.status == FileStatus.cancelled).label("cancelled"),
            func.count().filter(File.status == FileStatus.failed).label("failed"),
        )
        .select_from(File)
        .where(File.vector_store_id == store_id)
    )
    result = await session.execute(stmt)
    row = result.one()
    return FileCounts(
        total=row.total,
        in_progress=row.in_progress,
        completed=row.completed,
        cancelled=row.cancelled,
        failed=row.failed,
    )
