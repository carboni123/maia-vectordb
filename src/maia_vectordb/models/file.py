"""File database model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from maia_vectordb.db.base import Base

if TYPE_CHECKING:
    from maia_vectordb.models.file_chunk import FileChunk
    from maia_vectordb.models.vector_store import VectorStore


class FileStatus(str, enum.Enum):
    """Status of a file within a vector store."""

    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class File(Base):
    """A file uploaded to a vector store."""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vector_store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vector_stores.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String(1024))
    status: Mapped[FileStatus] = mapped_column(
        Enum(FileStatus, name="file_status"),
        default=FileStatus.in_progress,
    )
    bytes: Mapped[int] = mapped_column(Integer, default=0)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attributes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    purpose: Mapped[str] = mapped_column(String(64), default="assistants")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    vector_store: Mapped["VectorStore"] = relationship(
        "VectorStore", back_populates="files"
    )
    chunks: Mapped[list["FileChunk"]] = relationship(
        "FileChunk", back_populates="file", cascade="all, delete-orphan"
    )
