"""VectorStore database model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from maia_vectordb.db.base import Base

if TYPE_CHECKING:
    from maia_vectordb.models.file import File
    from maia_vectordb.models.file_chunk import FileChunk


class VectorStoreStatus(str, enum.Enum):
    """Status of a vector store."""

    expired = "expired"
    in_progress = "in_progress"
    completed = "completed"


class VectorStore(Base):
    """A named collection of file chunks with vector embeddings."""

    __tablename__ = "vector_stores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    metadata_: Mapped[dict[str, object] | None] = mapped_column(
        "metadata", JSON, nullable=True, default=None
    )
    file_counts: Mapped[dict[str, object] | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    status: Mapped[VectorStoreStatus] = mapped_column(
        Enum(VectorStoreStatus, name="vector_store_status"),
        default=VectorStoreStatus.completed,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    files: Mapped[list["File"]] = relationship(
        "File", back_populates="vector_store", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["FileChunk"]] = relationship(
        "FileChunk", back_populates="vector_store", cascade="all, delete-orphan"
    )
