"""File upload and processing endpoints."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.db.engine import get_db_session, get_session_factory
from maia_vectordb.models.file import File, FileStatus
from maia_vectordb.models.file_chunk import FileChunk
from maia_vectordb.models.vector_store import VectorStore
from maia_vectordb.schemas.file import FileUploadResponse
from maia_vectordb.services.chunking import split_text
from maia_vectordb.services.embedding import embed_texts

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/vector_stores/{vector_store_id}/files",
    tags=["files"],
)

DBSession = Annotated[AsyncSession, Depends(get_db_session)]

# Threshold (bytes) above which processing runs in a background task.
_BACKGROUND_THRESHOLD = 50_000


async def _validate_vector_store(
    session: AsyncSession, vector_store_id: uuid.UUID
) -> VectorStore:
    """Return the vector store or raise 404."""
    store = await session.get(VectorStore, vector_store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Vector store not found")
    return store


def _process_chunks_sync(
    text: str,
    file_id: uuid.UUID,
    vector_store_id: uuid.UUID,
) -> list[FileChunk]:
    """Chunk text, embed, and return FileChunk ORM objects (CPU/IO-bound)."""
    chunks = split_text(text)
    if not chunks:
        return []

    embeddings = embed_texts(chunks)

    return [
        FileChunk(
            id=uuid.uuid4(),
            file_id=file_id,
            vector_store_id=vector_store_id,
            chunk_index=idx,
            content=chunk_text,
            token_count=len(chunk_text.split()),
            embedding=emb,
        )
        for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings, strict=True))
    ]


async def _process_file_background(
    file_id: uuid.UUID,
    vector_store_id: uuid.UUID,
    text: str,
) -> None:
    """Background task: chunk, embed, and persist. Updates file status."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            chunk_objs = _process_chunks_sync(text, file_id, vector_store_id)
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


async def _read_upload_content(
    file: UploadFile | None,
    text: str | None,
) -> tuple[str, str, int]:
    """Extract (content, filename, byte_size) from upload or raw text."""
    if file is not None:
        raw = await file.read()
        content = raw.decode("utf-8")
        filename = file.filename or "upload.txt"
        return content, filename, len(raw)

    if text is not None:
        encoded = text.encode("utf-8")
        return text, "raw_text.txt", len(encoded)

    raise HTTPException(
        status_code=400,
        detail="Provide either a file upload or a 'text' field.",
    )


@router.post("", status_code=201, response_model=FileUploadResponse)
async def upload_file(
    vector_store_id: uuid.UUID,
    session: DBSession,
    background_tasks: BackgroundTasks,
    file: UploadFile | None = None,
    text: Annotated[str | None, Form()] = None,
) -> Any:
    """Upload a file (or raw text) to a vector store.

    The file is chunked, embedded, and stored as searchable vectors.
    Large files (>50 KB) are processed in the background.
    """
    # 1. Validate vector store exists
    await _validate_vector_store(session, vector_store_id)

    # 2. Read content
    content, filename, byte_size = await _read_upload_content(file, text)

    # 3. Create File record
    file_record = File(
        vector_store_id=vector_store_id,
        filename=filename,
        status=FileStatus.in_progress,
        bytes=byte_size,
    )
    session.add(file_record)
    await session.commit()
    await session.refresh(file_record)

    # 4. Process: inline for small files, background for large ones
    if byte_size > _BACKGROUND_THRESHOLD:
        background_tasks.add_task(
            _process_file_background,
            file_record.id,
            vector_store_id,
            content,
        )
        return FileUploadResponse.from_orm_model(file_record, chunk_count=0)

    # Inline processing for small files
    try:
        chunk_objs = _process_chunks_sync(content, file_record.id, vector_store_id)
        session.add_all(chunk_objs)
        file_record.status = FileStatus.completed
        await session.commit()
        await session.refresh(file_record)
        return FileUploadResponse.from_orm_model(
            file_record, chunk_count=len(chunk_objs)
        )
    except Exception:
        logger.exception("Failed to process file %s", file_record.id)
        file_record.status = FileStatus.failed
        await session.commit()
        await session.refresh(file_record)
        return FileUploadResponse.from_orm_model(file_record, chunk_count=0)


@router.get("/{file_id}", response_model=FileUploadResponse)
async def get_file(
    vector_store_id: uuid.UUID,
    file_id: uuid.UUID,
    session: DBSession,
) -> FileUploadResponse:
    """Retrieve a file's status (useful for polling background uploads)."""
    await _validate_vector_store(session, vector_store_id)

    file_obj = await session.get(File, file_id)
    if file_obj is None or file_obj.vector_store_id != vector_store_id:
        raise HTTPException(status_code=404, detail="File not found")

    # Count chunks
    stmt = select(FileChunk.id).where(FileChunk.file_id == file_id)
    result = await session.execute(stmt)
    chunk_count = len(result.all())

    return FileUploadResponse.from_orm_model(file_obj, chunk_count=chunk_count)
