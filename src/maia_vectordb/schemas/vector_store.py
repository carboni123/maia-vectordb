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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "in_progress": 0,
                    "completed": 3,
                    "cancelled": 0,
                    "failed": 0,
                    "total": 3,
                }
            ]
        }
    }


class CreateVectorStoreRequest(BaseModel):
    """Request body for creating a vector store."""

    name: str
    metadata: dict[str, Any] | None = None
    expires_after: dict[str, Any] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "my-knowledge-base",
                    "metadata": {"project": "chatbot"},
                    "expires_after": None,
                }
            ]
        }
    }


class VectorStoreResponse(BaseModel):
    """Response body representing a vector store (OpenAI format)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "object": "vector_store",
                    "name": "my-knowledge-base",
                    "status": "completed",
                    "file_counts": {
                        "in_progress": 0,
                        "completed": 3,
                        "cancelled": 0,
                        "failed": 0,
                        "total": 3,
                    },
                    "metadata": {"project": "chatbot"},
                    "created_at": 1700000000,
                    "updated_at": 1700000060,
                    "expires_at": None,
                }
            ]
        },
    )

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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "object": "list",
                    "data": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "object": "vector_store",
                            "name": "my-knowledge-base",
                            "status": "completed",
                            "file_counts": {
                                "in_progress": 0,
                                "completed": 3,
                                "cancelled": 0,
                                "failed": 0,
                                "total": 3,
                            },
                            "metadata": None,
                            "created_at": 1700000000,
                            "updated_at": 1700000060,
                            "expires_at": None,
                        }
                    ],
                    "first_id": "550e8400-e29b-41d4-a716-446655440000",
                    "last_id": "550e8400-e29b-41d4-a716-446655440000",
                    "has_more": False,
                }
            ]
        }
    }


class DeleteVectorStoreResponse(BaseModel):
    """Response body for deleting a vector store."""

    id: str
    object: str = Field(default="vector_store.deleted")
    deleted: bool = True

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "object": "vector_store.deleted",
                    "deleted": True,
                }
            ]
        }
    }
