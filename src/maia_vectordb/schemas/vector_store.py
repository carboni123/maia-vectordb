"""Pydantic schemas for vector store API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FileCounts(BaseModel):
    """File processing counts for a vector store."""

    in_progress: int = 0
    completed: int = 0
    cancelled: int = 0
    failed: int = 0
    total: int = 0

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "in_progress": 0,
                    "completed": 3,
                    "cancelled": 0,
                    "failed": 0,
                    "total": 3,
                }
            ]
        },
    )


class ExpiresAfter(BaseModel):
    """Expiration policy for a vector store (OpenAI format).

    ``anchor`` is always ``"last_active_at"`` (the only value OpenAI
    supports). ``days`` is the number of days after last activity before
    the store expires.
    """

    anchor: str = "last_active_at"
    days: int = Field(ge=1)


class CreateVectorStoreRequest(BaseModel):
    """Request body for creating a vector store."""

    name: str = Field(min_length=1)
    metadata: dict[str, Any] | None = None
    expires_after: ExpiresAfter | None = None

    @field_validator("expires_after", mode="before")
    @classmethod
    def _parse_expires_after(
        cls, v: Any,
    ) -> Any:
        """Accept both ``ExpiresAfter`` and a plain dict."""
        if isinstance(v, dict):
            anchor = v.get("anchor", "last_active_at")
            if anchor != "last_active_at":
                raise ValueError(
                    f"Unsupported anchor '{anchor}'. "
                    "Only 'last_active_at' is supported."
                )
        return v

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "my-knowledge-base",
                    "metadata": {"project": "chatbot"},
                    "expires_after": {"anchor": "last_active_at", "days": 7},
                }
            ]
        },
    )


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
        *,
        file_counts: "FileCounts | None" = None,
    ) -> "VectorStoreResponse":
        """Build response from a VectorStore ORM instance.

        Parameters
        ----------
        obj:
            VectorStore ORM model.
        file_counts:
            Pre-computed file counts. If ``None``, falls back to the
            JSON column on the model (for backwards compatibility),
            or returns zeros.
        """
        obj_id = getattr(obj, "id")
        obj_name: str = getattr(obj, "name")
        obj_status = getattr(obj, "status")
        obj_metadata: dict[str, Any] | None = getattr(obj, "metadata_")
        obj_created_at: datetime = getattr(obj, "created_at")
        obj_updated_at: datetime = getattr(obj, "updated_at")
        obj_expires_at: datetime | None = getattr(obj, "expires_at")

        if file_counts is None:
            raw_counts: dict[str, Any] | None = getattr(
                obj, "file_counts", None,
            )
            file_counts = (
                FileCounts(**raw_counts)
                if raw_counts is not None
                else FileCounts()
            )

        return cls(
            id=str(obj_id),
            name=obj_name,
            status=(
                obj_status.value
                if hasattr(obj_status, "value")
                else str(obj_status)
            ),
            file_counts=file_counts,
            metadata=obj_metadata,
            created_at=int(obj_created_at.timestamp()),
            updated_at=int(obj_updated_at.timestamp()),
            expires_at=(
                int(obj_expires_at.timestamp())
                if obj_expires_at
                else None
            ),
        )


class VectorStoreListResponse(BaseModel):
    """Paginated list of vector stores (OpenAI format)."""

    object: str = Field(default="list")
    data: list["VectorStoreResponse"]
    first_id: str | None = None
    last_id: str | None = None
    has_more: bool = False

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
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
        },
    )


class DeleteVectorStoreResponse(BaseModel):
    """Response body for deleting a vector store."""

    id: str
    object: str = Field(default="vector_store.deleted")
    deleted: bool = True

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "object": "vector_store.deleted",
                    "deleted": True,
                }
            ]
        },
    )
