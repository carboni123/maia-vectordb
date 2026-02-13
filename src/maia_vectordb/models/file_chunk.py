"""FileChunk database model with pgvector embedding."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from maia_vectordb.db.base import Base

if TYPE_CHECKING:
    from maia_vectordb.models.file import File
    from maia_vectordb.models.vector_store import VectorStore

EMBEDDING_DIMENSION = 1536


class FileChunk(Base):
    """A chunk of text from a file, with its vector embedding."""

    __tablename__ = "file_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE")
    )
    vector_store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vector_stores.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[Any] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    metadata_: Mapped[dict[str, object] | None] = mapped_column(
        "metadata", JSON, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    file: Mapped["File"] = relationship(
        "File", back_populates="chunks"
    )
    vector_store: Mapped["VectorStore"] = relationship(
        "VectorStore", back_populates="chunks"
    )

    __table_args__ = (
        Index(
            "ix_file_chunks_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
