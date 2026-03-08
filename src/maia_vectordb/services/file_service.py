"""Service layer for file processing operations."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.core.exceptions import NotFoundError, ValidationError
from maia_vectordb.db.engine import get_session_factory
from maia_vectordb.models.file import File, FileStatus
from maia_vectordb.models.file_chunk import FileChunk
from maia_vectordb.services.chunking import get_encoding, split_text
from maia_vectordb.services.embedding import embed_texts
from maia_vectordb.services.extraction import (
    detect_file_type,
    extract_text,
    is_binary_format,
)

logger = logging.getLogger(__name__)

# Threshold (bytes) above which processing runs in a background task.
BACKGROUND_THRESHOLD = 50_000

CONTENT_TYPE_MAP: dict[str, str] = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".html": "text/html",
    ".htm": "text/html",
    ".csv": "text/csv",
    ".xml": "application/xml",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
}


def read_upload_content(
    raw_bytes: bytes | None,
    raw_text: str | None,
    filename: str,
) -> tuple[str, str | None]:
    """Extract text content from upload bytes or raw text.

    Returns
    -------
    tuple[str, str | None]
        (extracted_text, content_type).
    """
    if raw_bytes is not None:
        ext = detect_file_type(filename)
        content_type = CONTENT_TYPE_MAP.get(ext)
        if is_binary_format(ext):
            return extract_text(raw_bytes, ext), content_type
        try:
            return raw_bytes.decode("utf-8"), content_type
        except UnicodeDecodeError as exc:
            raise ValidationError(
                f"File '{filename}' is not valid UTF-8 text. "
                "For binary formats, use a supported extension "
                "(.pdf, .docx)."
            ) from exc

    if raw_text is not None:
        ext = detect_file_type(filename)
        content_type = CONTENT_TYPE_MAP.get(ext)
        return raw_text, content_type

    raise ValidationError("Provide either a file upload or a 'text' field.")


async def create_file(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
    filename: str,
    byte_size: int,
    content_type: str | None,
    attributes: dict[str, Any] | None = None,
) -> File:
    """Create a File record in the database."""
    file_record = File(
        vector_store_id=vector_store_id,
        filename=filename,
        status=FileStatus.in_progress,
        bytes=byte_size,
        content_type=content_type,
        attributes=attributes,
    )
    session.add(file_record)
    await session.commit()
    await session.refresh(file_record)
    return file_record


async def process_file_inline(
    session: AsyncSession,
    file_record: File,
    content: str,
    vector_store_id: uuid.UUID,
) -> int:
    """Process a file synchronously: chunk, embed, persist.

    Updates the file status to completed/failed. Returns chunk count.
    """
    chunk_objs = await process_chunks(content, file_record.id, vector_store_id)
    session.add_all(chunk_objs)
    file_record.status = FileStatus.completed
    await session.commit()
    await session.refresh(file_record)
    return len(chunk_objs)


async def process_chunks(
    text: str,
    file_id: uuid.UUID,
    vector_store_id: uuid.UUID,
) -> list[FileChunk]:
    """Chunk text, embed, and return FileChunk ORM objects."""
    chunks = split_text(text)
    if not chunks:
        return []

    embeddings = await embed_texts(chunks)

    return [
        FileChunk(
            id=uuid.uuid4(),
            file_id=file_id,
            vector_store_id=vector_store_id,
            chunk_index=idx,
            content=chunk_text,
            token_count=len(get_encoding().encode(chunk_text)),
            embedding=emb,
        )
        for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings, strict=True))
    ]


async def process_file_background(
    file_id: uuid.UUID,
    vector_store_id: uuid.UUID,
    text: str,
) -> None:
    """Background task: chunk, embed, and persist. Updates file status."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            chunk_objs = await process_chunks(text, file_id, vector_store_id)
            session.add_all(chunk_objs)

            file_obj = await session.get(File, file_id)
            if file_obj is not None:
                file_obj.status = FileStatus.completed
            await session.commit()
            logger.info(
                "Background processing complete for file %s (%d chunks)",
                file_id,
                len(chunk_objs),
            )
        except Exception:
            logger.exception("Background processing failed for file %s", file_id)
            try:
                await session.rollback()
                file_obj = await session.get(File, file_id)
                if file_obj is not None:
                    file_obj.status = FileStatus.failed
                await session.commit()
            except Exception:
                logger.exception("Failed to mark file %s as failed", file_id)


async def list_files(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    order: str = "desc",
) -> tuple[list[tuple[File, int]], bool]:
    """List files in a vector store with chunk counts.

    Returns
    -------
    tuple[list[tuple[File, int]], bool]
        (list of (file, chunk_count) tuples, has_more flag).
    """
    order_col = File.created_at.asc() if order == "asc" else File.created_at.desc()
    file_stmt = (
        select(File)
        .where(File.vector_store_id == vector_store_id)
        .order_by(order_col)
        .offset(offset)
        .limit(limit + 1)
    )
    result = await session.execute(file_stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    files = rows[:limit]

    items: list[tuple[File, int]] = []
    for f in files:
        count_stmt = (
            select(func.count()).select_from(FileChunk).where(FileChunk.file_id == f.id)
        )
        count_result = await session.execute(count_stmt)
        items.append((f, count_result.scalar_one()))

    return items, has_more


async def get_file(
    session: AsyncSession,
    file_id: uuid.UUID,
    vector_store_id: uuid.UUID,
) -> tuple[File, int]:
    """Retrieve a file and its chunk count.

    Returns
    -------
    tuple[File, int]
        (file ORM object, chunk_count).

    Raises
    ------
    NotFoundError
        If the file does not exist or belongs to a different store.
    """
    file_obj = await session.get(File, file_id)
    if file_obj is None or file_obj.vector_store_id != vector_store_id:
        raise NotFoundError("File not found")

    stmt = (
        select(func.count()).select_from(FileChunk).where(FileChunk.file_id == file_id)
    )
    result = await session.execute(stmt)
    chunk_count = result.scalar_one()

    return file_obj, chunk_count


async def delete_file(
    session: AsyncSession,
    file_id: uuid.UUID,
    vector_store_id: uuid.UUID,
) -> str:
    """Delete a file and its chunks from a vector store.

    Returns
    -------
    str
        The file ID as a string.

    Raises
    ------
    NotFoundError
        If the file does not exist or belongs to a different store.
    """
    file_obj = await session.get(File, file_id)
    if file_obj is None or file_obj.vector_store_id != vector_store_id:
        raise NotFoundError("File not found")

    await session.delete(file_obj)  # CASCADE deletes chunks
    await session.commit()

    return str(file_id)
