"""Service layer for file processing operations."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.core.exceptions import NotFoundError
from maia_vectordb.db.engine import get_session_factory
from maia_vectordb.models.file import File, FileStatus
from maia_vectordb.models.file_chunk import FileChunk
from maia_vectordb.services.chunking import get_encoding, split_text
from maia_vectordb.services.embedding import embed_texts

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
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


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
            file_obj = await session.get(File, file_id)
            if file_obj is not None:
                file_obj.status = FileStatus.failed
            await session.commit()


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
        select(func.count())
        .select_from(FileChunk)
        .where(FileChunk.file_id == file_id)
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
