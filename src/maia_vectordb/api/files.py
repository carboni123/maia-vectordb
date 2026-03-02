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
    EmbeddingServiceError,
    FileTooLargeError,
    ValidationError,
)
from maia_vectordb.models.file import File, FileStatus
from maia_vectordb.schemas.file import DeleteFileResponse, FileUploadResponse
from maia_vectordb.services import file_service, vector_store_service
from maia_vectordb.services.extraction import (
    detect_file_type,
    extract_text,
    is_binary_format,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/vector_stores/{vector_store_id}/files",
    tags=["files"],
)


async def _read_upload_content(
    file: UploadFile | None,
    text: str | None,
    filename_override: str | None = None,
) -> tuple[str, str, int, str | None]:
    """Extract (content, filename, byte_size, content_type) from upload or raw text."""
    if file is not None:
        raw = await file.read()
        fname = filename_override or file.filename or "upload.txt"
        ext = detect_file_type(fname)
        content_type = file_service.CONTENT_TYPE_MAP.get(ext)

        if is_binary_format(ext):
            content = extract_text(raw, ext)
        else:
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValidationError(
                    f"File '{fname}' is not valid UTF-8 text. "
                    "For binary formats, use a supported extension (.pdf, .docx)."
                ) from exc

        return content, fname, len(raw), content_type

    if text is not None:
        fname = filename_override or "raw_text.txt"
        encoded = text.encode("utf-8")
        ext = detect_file_type(fname)
        content_type = file_service.CONTENT_TYPE_MAP.get(ext)
        return text, fname, len(encoded), content_type

    raise ValidationError("Provide either a file upload or a 'text' field.")


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
            raise ValidationError("Invalid JSON in 'attributes' field.") from exc
        if not isinstance(parsed_attributes, dict):
            raise ValidationError("'attributes' must be a JSON object.")

    # 2. Read content
    content, resolved_filename, byte_size, content_type = await _read_upload_content(
        file, text, filename
    )

    # 2a. Enforce upload size limit
    if byte_size > settings.max_file_size_bytes:
        raise FileTooLargeError(
            f"File size {byte_size} bytes exceeds the limit of "
            f"{settings.max_file_size_bytes} bytes."
        )

    # 3. Create File record
    file_record = File(
        vector_store_id=vector_store_id,
        filename=resolved_filename,
        status=FileStatus.in_progress,
        bytes=byte_size,
        content_type=content_type,
        attributes=parsed_attributes,
    )
    session.add(file_record)
    await session.commit()
    await session.refresh(file_record)

    # 4. Process: inline for small files, background for large ones
    if byte_size > file_service.BACKGROUND_THRESHOLD:
        background_tasks.add_task(
            file_service.process_file_background,
            file_record.id,
            vector_store_id,
            content,
        )
        return FileUploadResponse.from_orm_model(file_record, chunk_count=0)

    # Inline processing for small files
    try:
        chunk_objs = await file_service.process_chunks(
            content, file_record.id, vector_store_id
        )
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
    deleted_id = await file_service.delete_file(session, file_id, vector_store_id)
    return DeleteFileResponse(id=deleted_id)
