"""File upload and processing endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Form,
    UploadFile,
)

from maia_vectordb.api.deps import DBSession
from maia_vectordb.core.config import settings
from maia_vectordb.core.exceptions import (
    APIError,
    EmbeddingServiceError,
    FileTooLargeError,
    ValidationError,
)
from maia_vectordb.models.file import FileStatus
from maia_vectordb.schemas.file import DeleteFileResponse, FileUploadResponse
from maia_vectordb.services import file_service, vector_store_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/vector_stores/{vector_store_id}/files",
    tags=["files"],
)


@router.post("", status_code=201, response_model=FileUploadResponse)
async def upload_file(
    vector_store_id: uuid.UUID,
    session: DBSession,
    background_tasks: BackgroundTasks,
    file: UploadFile | None = None,
    text: Annotated[str | None, Form()] = None,
    filename: Annotated[str | None, Form()] = None,
    attributes: Annotated[str | None, Form()] = None,
) -> FileUploadResponse:
    """Upload a file (or raw text) to a vector store.

    The file is chunked, embedded, and stored as searchable vectors.
    Large files (>50 KB) are processed in the background.
    """
    # 1. Validate vector store exists
    await vector_store_service.get_vector_store(session, vector_store_id)

    # 1a. Parse attributes JSON
    parsed_attributes: dict[str, Any] | None = None
    if attributes is not None:
        try:
            parsed_attributes = json.loads(attributes)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValidationError(
                "Invalid JSON in 'attributes' field."
            ) from exc
        if not isinstance(parsed_attributes, dict):
            raise ValidationError("'attributes' must be a JSON object.")

    # 2. Read content via service layer
    raw_bytes: bytes | None = None
    if file is not None:
        raw_bytes = await file.read()
    resolved_filename = filename or (
        file.filename if file is not None else None
    ) or (
        "raw_text.txt" if text is not None else "upload.txt"
    )
    content, content_type = file_service.read_upload_content(
        raw_bytes, text, resolved_filename,
    )
    byte_size = len(raw_bytes) if raw_bytes is not None else len(
        content.encode("utf-8")
    )

    # 2a. Enforce upload size limit
    if byte_size > settings.max_file_size_bytes:
        raise FileTooLargeError(
            f"File size {byte_size} bytes exceeds the limit of "
            f"{settings.max_file_size_bytes} bytes."
        )

    # 3. Create File record via service
    file_record = await file_service.create_file(
        session,
        vector_store_id=vector_store_id,
        filename=resolved_filename,
        byte_size=byte_size,
        content_type=content_type,
        attributes=parsed_attributes,
    )

    # 4. Process: inline for small files, background for large ones
    if byte_size > file_service.BACKGROUND_THRESHOLD:
        background_tasks.add_task(
            file_service.process_file_background,
            file_record.id,
            vector_store_id,
            content,
        )
        return FileUploadResponse.from_orm_model(
            file_record, chunk_count=0,
        )

    # Inline processing via service
    try:
        chunk_count = await file_service.process_file_inline(
            session, file_record, content, vector_store_id,
        )
        return FileUploadResponse.from_orm_model(
            file_record, chunk_count=chunk_count,
        )
    except APIError:
        file_record.status = FileStatus.failed
        await session.commit()
        raise
    except Exception:
        logger.exception("Failed to process file %s", file_record.id)
        file_record.status = FileStatus.failed
        await session.commit()
        raise EmbeddingServiceError("File processing failed")


@router.get("/{file_id}", response_model=FileUploadResponse)
async def get_file(
    vector_store_id: uuid.UUID,
    file_id: uuid.UUID,
    session: DBSession,
) -> FileUploadResponse:
    """Retrieve a file's status (useful for polling background uploads)."""
    await vector_store_service.get_vector_store(session, vector_store_id)
    file_obj, chunk_count = await file_service.get_file(
        session, file_id, vector_store_id
    )
    return FileUploadResponse.from_orm_model(file_obj, chunk_count=chunk_count)


@router.delete("/{file_id}", response_model=DeleteFileResponse)
async def delete_file(
    vector_store_id: uuid.UUID,
    file_id: uuid.UUID,
    session: DBSession,
) -> DeleteFileResponse:
    """Delete a file and its chunks from a vector store."""
    await vector_store_service.get_vector_store(session, vector_store_id)
    deleted_id = await file_service.delete_file(
        session, file_id, vector_store_id,
    )
    return DeleteFileResponse(id=deleted_id)
