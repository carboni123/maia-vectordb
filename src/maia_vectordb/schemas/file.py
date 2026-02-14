"""Pydantic schemas for file API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FileUploadResponse(BaseModel):
    """Response body representing a file in a vector store (OpenAI format)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "660e8400-e29b-41d4-a716-446655440001",
                    "object": "vector_store.file",
                    "vector_store_id": "550e8400-e29b-41d4-a716-446655440000",
                    "filename": "document.txt",
                    "status": "completed",
                    "bytes": 2048,
                    "chunk_count": 5,
                    "purpose": "assistants",
                    "created_at": 1700000000,
                }
            ]
        },
    )

    id: str
    object: str = Field(default="vector_store.file")
    vector_store_id: str
    filename: str
    status: str
    bytes: int = 0
    chunk_count: int = 0
    purpose: str = "assistants"
    created_at: int

    @classmethod
    def from_orm_model(cls, obj: Any, *, chunk_count: int = 0) -> "FileUploadResponse":
        """Build response from a File ORM instance."""
        obj_id = getattr(obj, "id")
        obj_vs_id = getattr(obj, "vector_store_id")
        obj_filename: str = getattr(obj, "filename")
        obj_status = getattr(obj, "status")
        obj_bytes: int = getattr(obj, "bytes")
        obj_purpose: str = getattr(obj, "purpose")
        obj_created_at: datetime = getattr(obj, "created_at")

        return cls(
            id=str(obj_id),
            vector_store_id=str(obj_vs_id),
            filename=obj_filename,
            status=(
                obj_status.value if hasattr(obj_status, "value") else str(obj_status)
            ),
            bytes=obj_bytes,
            chunk_count=chunk_count,
            purpose=obj_purpose,
            created_at=int(obj_created_at.timestamp()),
        )


class FileListResponse(BaseModel):
    """Paginated list of files in a vector store (OpenAI format)."""

    object: str = Field(default="list")
    data: list["FileUploadResponse"]
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
                            "id": "660e8400-e29b-41d4-a716-446655440001",
                            "object": "vector_store.file",
                            "vector_store_id": "550e8400-e29b-41d4-a716-446655440000",
                            "filename": "document.txt",
                            "status": "completed",
                            "bytes": 2048,
                            "chunk_count": 5,
                            "purpose": "assistants",
                            "created_at": 1700000000,
                        }
                    ],
                    "first_id": "660e8400-e29b-41d4-a716-446655440001",
                    "last_id": "660e8400-e29b-41d4-a716-446655440001",
                    "has_more": False,
                }
            ]
        },
    )
