"""Vector store CRUD endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from maia_vectordb.api.deps import DBSession
from maia_vectordb.schemas.vector_store import (
    CreateVectorStoreRequest,
    DeleteVectorStoreResponse,
    VectorStoreListResponse,
    VectorStoreResponse,
)
from maia_vectordb.services import vector_store_service

router = APIRouter(prefix="/v1/vector_stores", tags=["vector_stores"])


@router.post("", status_code=201, response_model=VectorStoreResponse)
async def create_vector_store(
    body: CreateVectorStoreRequest,
    session: DBSession,
) -> VectorStoreResponse:
    """Create a new vector store."""
    store = await vector_store_service.create_vector_store(
        session=session,
        name=body.name,
        metadata=body.metadata,
        expires_after=body.expires_after,
    )
    counts = await vector_store_service.get_file_counts(
        session,
        store.id,
    )
    return VectorStoreResponse.from_orm_model(store, file_counts=counts)


@router.get("", response_model=VectorStoreListResponse)
async def list_vector_stores(
    session: DBSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> VectorStoreListResponse:
    """List vector stores with pagination."""
    stores, has_more = await vector_store_service.list_vector_stores(
        session=session,
        limit=limit,
        offset=offset,
        order=order,
    )

    data = []
    for s in stores:
        counts = await vector_store_service.get_file_counts(
            session,
            s.id,
        )
        data.append(VectorStoreResponse.from_orm_model(s, file_counts=counts))

    return VectorStoreListResponse(
        data=data,
        first_id=data[0].id if data else None,
        last_id=data[-1].id if data else None,
        has_more=has_more,
    )


@router.get("/{vector_store_id}", response_model=VectorStoreResponse)
async def get_vector_store(
    vector_store_id: UUID,
    session: DBSession,
) -> VectorStoreResponse:
    """Retrieve a single vector store by ID."""
    store = await vector_store_service.get_vector_store(
        session=session,
        store_id=vector_store_id,
    )
    counts = await vector_store_service.get_file_counts(
        session,
        store.id,
    )
    return VectorStoreResponse.from_orm_model(store, file_counts=counts)


@router.delete(
    "/{vector_store_id}",
    response_model=DeleteVectorStoreResponse,
)
async def delete_vector_store(
    vector_store_id: UUID,
    session: DBSession,
) -> DeleteVectorStoreResponse:
    """Delete a vector store and all its documents (cascade)."""
    store_id = await vector_store_service.delete_vector_store(
        session=session,
        store_id=vector_store_id,
    )
    return DeleteVectorStoreResponse(id=store_id)
