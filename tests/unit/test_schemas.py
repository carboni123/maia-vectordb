"""Comprehensive schema validation tests for all Pydantic models.

Covers: instantiation, from_orm_model classmethods, pagination wrappers,
validation boundaries, model_config, JSON serialization, and OpenAI-compatible
object type defaults.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, ValidationError

from maia_vectordb.models.file import FileStatus
from maia_vectordb.models.vector_store import VectorStoreStatus
from maia_vectordb.schemas.file import (
    DeleteFileResponse,
    FileListResponse,
    FileUploadResponse,
)
from maia_vectordb.schemas.search import SearchRequest, SearchResponse, SearchResult
from maia_vectordb.schemas.vector_store import (
    CreateVectorStoreRequest,
    DeleteVectorStoreResponse,
    FileCounts,
    VectorStoreListResponse,
    VectorStoreResponse,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
_NOW_EPOCH = int(_NOW.timestamp())


def _mock_store(
    *,
    status: VectorStoreStatus = VectorStoreStatus.completed,
    metadata_: dict[str, Any] | None = None,
    file_counts: dict[str, Any] | None = None,
    expires_at: datetime | None = None,
) -> MagicMock:
    """Create a mock VectorStore ORM instance."""
    m = MagicMock()
    m.id = uuid.uuid4()
    m.name = "test-store"
    m.status = status
    m.metadata_ = metadata_
    m.file_counts = file_counts
    m.created_at = _NOW
    m.updated_at = _NOW
    m.expires_at = expires_at
    return m


def _mock_file(
    *,
    status: FileStatus = FileStatus.completed,
) -> MagicMock:
    """Create a mock File ORM instance."""
    m = MagicMock()
    m.id = uuid.uuid4()
    m.vector_store_id = uuid.uuid4()
    m.filename = "doc.txt"
    m.status = status
    m.bytes = 2048
    m.purpose = "assistants"
    m.created_at = _NOW
    return m


# ===================================================================
# 1. model_config includes from_attributes=True on relevant models
# ===================================================================


class TestModelConfigFromAttributes:
    """AC-2: Verify from_attributes=True is set on relevant models."""

    @pytest.mark.parametrize(
        "model_cls",
        [
            FileCounts,
            CreateVectorStoreRequest,
            VectorStoreResponse,
            VectorStoreListResponse,
            DeleteVectorStoreResponse,
            FileUploadResponse,
            FileListResponse,
            SearchRequest,
            SearchResult,
            SearchResponse,
        ],
    )
    def test_from_attributes_enabled(self, model_cls: type[BaseModel]) -> None:
        """Every API schema has from_attributes=True in model_config."""
        cfg = model_cls.model_config
        assert cfg.get("from_attributes") is True, (
            f"{model_cls.__name__}.model_config missing from_attributes=True"
        )


# ===================================================================
# 2. OpenAI object type string defaults
# ===================================================================


class TestObjectTypeDefaults:
    """AC-3: Verify OpenAI-compatible object type strings."""

    def test_vector_store_response_object_default(self) -> None:
        resp = VectorStoreResponse(
            id="vs_1", name="s", status="completed", created_at=0, updated_at=0
        )
        assert resp.object == "vector_store"

    def test_vector_store_list_response_object_default(self) -> None:
        resp = VectorStoreListResponse(data=[])
        assert resp.object == "list"

    def test_delete_vector_store_response_object_default(self) -> None:
        resp = DeleteVectorStoreResponse(id="vs_1")
        assert resp.object == "vector_store.deleted"

    def test_file_upload_response_object_default(self) -> None:
        resp = FileUploadResponse(
            id="f_1",
            vector_store_id="vs_1",
            filename="a.txt",
            status="completed",
            created_at=0,
        )
        assert resp.object == "vector_store.file"

    def test_delete_file_response_object_default(self) -> None:
        resp = DeleteFileResponse(id="f_1")
        assert resp.object == "vector_store.file.deleted"
        assert resp.deleted is True

    def test_file_list_response_object_default(self) -> None:
        resp = FileListResponse(data=[])
        assert resp.object == "list"

    def test_search_response_object_default(self) -> None:
        resp = SearchResponse(data=[], search_query="q")
        assert resp.object == "list"


# ===================================================================
# 3. from_orm_model classmethods – VectorStoreResponse
# ===================================================================


class TestVectorStoreFromOrm:
    """AC-4: Timestamp conversion and ORM mapping for VectorStoreResponse."""

    def test_enum_status_converted_to_string(self) -> None:
        """Enum .value is extracted so JSON never contains the enum wrapper."""
        orm = _mock_store(status=VectorStoreStatus.in_progress)
        resp = VectorStoreResponse.from_orm_model(orm)
        assert resp.status == "in_progress"
        assert isinstance(resp.status, str)

    def test_expired_status(self) -> None:
        orm = _mock_store(status=VectorStoreStatus.expired)
        resp = VectorStoreResponse.from_orm_model(orm)
        assert resp.status == "expired"

    def test_completed_status(self) -> None:
        orm = _mock_store(status=VectorStoreStatus.completed)
        resp = VectorStoreResponse.from_orm_model(orm)
        assert resp.status == "completed"

    def test_none_metadata(self) -> None:
        orm = _mock_store(metadata_=None)
        resp = VectorStoreResponse.from_orm_model(orm)
        assert resp.metadata is None

    def test_populated_metadata(self) -> None:
        orm = _mock_store(metadata_={"project": "chatbot", "env": "prod"})
        resp = VectorStoreResponse.from_orm_model(orm)
        assert resp.metadata == {"project": "chatbot", "env": "prod"}

    def test_expires_at_present(self) -> None:
        """When expires_at is set, it is converted to epoch int."""
        exp = datetime(2026, 1, 1, tzinfo=UTC)
        orm = _mock_store(expires_at=exp)
        resp = VectorStoreResponse.from_orm_model(orm)
        assert resp.expires_at == int(exp.timestamp())

    def test_expires_at_absent(self) -> None:
        orm = _mock_store(expires_at=None)
        resp = VectorStoreResponse.from_orm_model(orm)
        assert resp.expires_at is None

    def test_datetime_to_epoch_conversion(self) -> None:
        """AC-4: created_at and updated_at are integer epoch seconds."""
        orm = _mock_store()
        resp = VectorStoreResponse.from_orm_model(orm)
        assert resp.created_at == _NOW_EPOCH
        assert resp.updated_at == _NOW_EPOCH
        assert isinstance(resp.created_at, int)
        assert isinstance(resp.updated_at, int)


# ===================================================================
# 4. from_orm_model classmethods – FileUploadResponse
# ===================================================================


class TestFileUploadFromOrm:
    """from_orm_model on FileUploadResponse with various ORM states."""

    def test_enum_status_in_progress(self) -> None:
        orm = _mock_file(status=FileStatus.in_progress)
        resp = FileUploadResponse.from_orm_model(orm, chunk_count=0)
        assert resp.status == "in_progress"

    def test_enum_status_failed(self) -> None:
        orm = _mock_file(status=FileStatus.failed)
        resp = FileUploadResponse.from_orm_model(orm, chunk_count=0)
        assert resp.status == "failed"

    def test_enum_status_cancelled(self) -> None:
        orm = _mock_file(status=FileStatus.cancelled)
        resp = FileUploadResponse.from_orm_model(orm, chunk_count=0)
        assert resp.status == "cancelled"

    def test_chunk_count_passed_through(self) -> None:
        orm = _mock_file()
        resp = FileUploadResponse.from_orm_model(orm, chunk_count=42)
        assert resp.chunk_count == 42

    def test_datetime_to_epoch(self) -> None:
        orm = _mock_file()
        resp = FileUploadResponse.from_orm_model(orm)
        assert resp.created_at == _NOW_EPOCH
        assert isinstance(resp.created_at, int)


# ===================================================================
# 5. Pagination wrappers
# ===================================================================


class TestPaginationWrappers:
    """VectorStoreListResponse and FileListResponse edge cases."""

    # --- VectorStoreListResponse ---

    def test_vector_store_list_empty(self) -> None:
        resp = VectorStoreListResponse(data=[])
        assert resp.data == []
        assert resp.first_id is None
        assert resp.last_id is None
        assert resp.has_more is False

    def test_vector_store_list_single_item(self) -> None:
        item = VectorStoreResponse(
            id="vs_1",
            name="s",
            status="completed",
            created_at=0,
            updated_at=0,
        )
        resp = VectorStoreListResponse(
            data=[item], first_id="vs_1", last_id="vs_1", has_more=False
        )
        assert len(resp.data) == 1
        assert resp.first_id == "vs_1"
        assert resp.last_id == "vs_1"

    def test_vector_store_list_max_pagination(self) -> None:
        """Simulate a full page with has_more=True."""
        items = [
            VectorStoreResponse(
                id=f"vs_{i}",
                name=f"store-{i}",
                status="completed",
                created_at=0,
                updated_at=0,
            )
            for i in range(20)
        ]
        resp = VectorStoreListResponse(
            data=items,
            first_id="vs_0",
            last_id="vs_19",
            has_more=True,
        )
        assert len(resp.data) == 20
        assert resp.has_more is True
        assert resp.first_id == "vs_0"
        assert resp.last_id == "vs_19"

    # --- FileListResponse ---

    def test_file_list_empty(self) -> None:
        resp = FileListResponse(data=[])
        assert resp.data == []
        assert resp.first_id is None
        assert resp.has_more is False

    def test_file_list_single_item(self) -> None:
        item = FileUploadResponse(
            id="f_1",
            vector_store_id="vs_1",
            filename="a.txt",
            status="completed",
            created_at=0,
        )
        resp = FileListResponse(
            data=[item], first_id="f_1", last_id="f_1", has_more=False
        )
        assert len(resp.data) == 1

    def test_file_list_max_pagination(self) -> None:
        items = [
            FileUploadResponse(
                id=f"f_{i}",
                vector_store_id="vs_1",
                filename=f"file_{i}.txt",
                status="completed",
                created_at=0,
            )
            for i in range(20)
        ]
        resp = FileListResponse(
            data=items, first_id="f_0", last_id="f_19", has_more=True
        )
        assert len(resp.data) == 20
        assert resp.has_more is True


# ===================================================================
# 6. SearchRequest validation boundaries
# ===================================================================


class TestSearchRequestValidation:
    """Boundary validation for SearchRequest fields."""

    def test_max_results_min_boundary_accepted(self) -> None:
        req = SearchRequest(query="q", max_results=1)
        assert req.max_results == 1

    def test_max_results_max_boundary_accepted(self) -> None:
        req = SearchRequest(query="q", max_results=100)
        assert req.max_results == 100

    def test_max_results_above_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchRequest(query="q", max_results=101)

    def test_max_results_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchRequest(query="q", max_results=0)

    def test_default_max_results(self) -> None:
        req = SearchRequest(query="q")
        assert req.max_results == 10

    def test_score_threshold_none_allowed(self) -> None:
        req = SearchRequest(query="q")
        assert req.score_threshold is None

    def test_filter_dict_accepted(self) -> None:
        req = SearchRequest(query="q", filter={"source": "docs"})
        assert req.filter == {"source": "docs"}


# ===================================================================
# 7. JSON serialization – OpenAI-compatible field names (AC-5)
# ===================================================================


class TestJsonSerializationFormat:
    """AC-5: JSON output matches OpenAI format with no snake_case leaks."""

    def test_vector_store_response_json_keys(self) -> None:
        orm = _mock_store(file_counts={"total": 1, "completed": 1})
        resp = VectorStoreResponse.from_orm_model(orm)
        data = json.loads(resp.model_dump_json())

        expected_keys = {
            "id",
            "object",
            "name",
            "status",
            "file_counts",
            "metadata",
            "created_at",
            "updated_at",
            "expires_at",
        }
        assert set(data.keys()) == expected_keys
        assert data["object"] == "vector_store"
        # Nested file_counts keys
        fc_keys = {"in_progress", "completed", "cancelled", "failed", "total"}
        assert set(data["file_counts"].keys()) == fc_keys

    def test_file_upload_response_json_keys(self) -> None:
        orm = _mock_file()
        resp = FileUploadResponse.from_orm_model(orm, chunk_count=5)
        data = json.loads(resp.model_dump_json())

        expected_keys = {
            "id",
            "object",
            "vector_store_id",
            "filename",
            "status",
            "bytes",
            "chunk_count",
            "content_type",
            "attributes",
            "purpose",
            "created_at",
        }
        assert set(data.keys()) == expected_keys
        assert data["object"] == "vector_store.file"

    def test_delete_response_json_keys(self) -> None:
        resp = DeleteVectorStoreResponse(id="vs_1")
        data = json.loads(resp.model_dump_json())

        assert set(data.keys()) == {"id", "object", "deleted"}
        assert data["object"] == "vector_store.deleted"
        assert data["deleted"] is True

    def test_vector_store_list_json_keys(self) -> None:
        resp = VectorStoreListResponse(data=[], first_id=None, last_id=None)
        data = json.loads(resp.model_dump_json())

        expected_keys = {"object", "data", "first_id", "last_id", "has_more"}
        assert set(data.keys()) == expected_keys
        assert data["object"] == "list"

    def test_search_response_json_keys(self) -> None:
        result = SearchResult(file_id="f_1", chunk_index=0, content="text", score=0.9)
        resp = SearchResponse(data=[result], search_query="q")
        data = json.loads(resp.model_dump_json())

        assert set(data.keys()) == {"object", "data", "search_query"}
        assert data["object"] == "list"
        # Check nested result keys
        r = data["data"][0]
        expected_result_keys = {
            "file_id",
            "filename",
            "chunk_index",
            "content",
            "score",
            "metadata",
            "file_attributes",
        }
        assert set(r.keys()) == expected_result_keys

    def test_timestamps_are_integers_in_json(self) -> None:
        """Timestamps in JSON output must be integer epoch seconds, not ISO strings."""
        orm = _mock_store()
        resp = VectorStoreResponse.from_orm_model(orm)
        data = json.loads(resp.model_dump_json())

        assert isinstance(data["created_at"], int)
        assert isinstance(data["updated_at"], int)


# ===================================================================
# 8. Schema instantiation with valid data (all models)
# ===================================================================


class TestSchemaInstantiation:
    """All schema models can be instantiated with valid data."""

    def test_file_counts(self) -> None:
        fc = FileCounts(in_progress=1, completed=2, cancelled=0, failed=0, total=3)
        assert fc.total == 3

    def test_create_vector_store_request(self) -> None:
        req = CreateVectorStoreRequest(name="kb")
        assert req.name == "kb"
        assert req.metadata is None

    def test_create_vector_store_request_with_all_fields(self) -> None:
        req = CreateVectorStoreRequest(
            name="kb",
            metadata={"k": "v"},
            expires_after={"anchor": "last_active_at", "days": 7},
        )
        assert req.metadata == {"k": "v"}
        assert req.expires_after is not None

    def test_search_result(self) -> None:
        sr = SearchResult(
            file_id="f_1",
            filename="test.txt",
            chunk_index=0,
            content="hello",
            score=0.95,
            metadata={"src": "web"},
        )
        assert sr.score == 0.95

    def test_search_request_minimal(self) -> None:
        req = SearchRequest(query="hello world")
        assert req.query == "hello world"
        assert req.max_results == 10
        assert req.filter is None
        assert req.score_threshold is None
