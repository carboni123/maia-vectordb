"""Service layer for vector store CRUD operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.core.exceptions import NotFoundError
from maia_vectordb.models.vector_store import VectorStore


async def create_vector_store(
    session: AsyncSession,
    name: str,
    metadata: dict[str, object] | None = None,
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

    Returns
    -------
    VectorStore
        Newly created vector store ORM model.
    """
    store = VectorStore(name=name, metadata_=metadata)
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
    await session.delete(store)
    await session.commit()
    return store_id_str
