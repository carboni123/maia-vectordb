"""Pydantic schemas for vector store API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FileCounts(BaseModel):
    """File processing counts for a vector store."""

    in_progress: int = 0
    completed: int = 0
    cancelled: int = 0
    failed: int = 0
    total: int = 0


class CreateVectorStoreRequest(BaseModel):
    """Request body for creating a vector store."""

    name: str
    metadata: dict[str, Any] | None = None
    expires_after: dict[str, Any] | None = None


class VectorStoreResponse(BaseModel):
    """Response body representing a vector store (OpenAI format)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    object: str = Field(default="vector_store")
    name: str
    status: str
    file_counts: FileCounts = Field(default_factory=FileCounts)
    metadata: dict[str, Any] | None = None
    created_at: int
    updated_at: int
    expires_at: int | None = None

    @classmethod
    def from_orm_model(
        cls,
        obj: Any,
    ) -> "VectorStoreResponse":
        """Build response from a VectorStore ORM instance."""
        # Access attributes via getattr for type safety
        obj_id = getattr(obj, "id")
        obj_name: str = getattr(obj, "name")
        obj_status = getattr(obj, "status")
        obj_metadata: dict[str, Any] | None = getattr(obj, "metadata_")
        obj_file_counts: dict[str, Any] | None = getattr(obj, "file_counts")
        obj_created_at: datetime = getattr(obj, "created_at")
        obj_updated_at: datetime = getattr(obj, "updated_at")
        obj_expires_at: datetime | None = getattr(obj, "expires_at")

        file_counts = FileCounts()
        if obj_file_counts is not None:
            file_counts = FileCounts(**obj_file_counts)

        return cls(
            id=str(obj_id),
            name=obj_name,
            status=(
                obj_status.value if hasattr(obj_status, "value") else str(obj_status)
            ),
            file_counts=file_counts,
            metadata=obj_metadata,
            created_at=int(obj_created_at.timestamp()),
            updated_at=int(obj_updated_at.timestamp()),
            expires_at=int(obj_expires_at.timestamp()) if obj_expires_at else None,
        )


class VectorStoreListResponse(BaseModel):
    """Paginated list of vector stores (OpenAI format)."""

    object: str = Field(default="list")
    data: list["VectorStoreResponse"]
    first_id: str | None = None
    last_id: str | None = None
    has_more: bool = False


class DeleteVectorStoreResponse(BaseModel):
    """Response body for deleting a vector store."""

    id: str
    object: str = Field(default="vector_store.deleted")
    deleted: bool = True
