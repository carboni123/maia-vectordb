"""Tests for schema edge cases and validation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest


class TestVectorStoreSchemaEdgeCases:
    """Edge case tests for VectorStore schema."""

    def test_from_orm_with_none_file_counts(self) -> None:
        """VectorStoreResponse.from_orm_model handles None file_counts."""
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        # Mock ORM object with None file_counts
        mock_orm = MagicMock()
        mock_orm.id = uuid.uuid4()
        mock_orm.name = "Test Store"
        mock_orm.status = "active"
        mock_orm.file_counts = None  # This is what gets read by getattr
        mock_orm.created_at = datetime.now(timezone.utc)
        mock_orm.updated_at = datetime.now(timezone.utc)
        mock_orm.expires_at = None
        mock_orm.metadata_ = {}

        # Call from_orm_model
        result = VectorStoreResponse.from_orm_model(mock_orm)

        # Verify default empty FileCounts is used
        assert result.file_counts.total == 0
        assert result.file_counts.completed == 0
        assert result.file_counts.in_progress == 0
        assert result.file_counts.failed == 0

    def test_from_orm_with_empty_file_counts_dict(self) -> None:
        """VectorStoreResponse.from_orm_model handles empty file_counts dict."""
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        # Mock ORM object
        mock_orm = MagicMock()
        mock_orm.id = uuid.uuid4()
        mock_orm.name = "Test Store"
        mock_orm.status = "active"
        mock_orm.file_counts = {}
        mock_orm.created_at = datetime.now(timezone.utc)
        mock_orm.updated_at = datetime.now(timezone.utc)
        mock_orm.expires_at = None
        mock_orm.metadata_ = {}

        # Call from_orm_model
        result = VectorStoreResponse.from_orm_model(mock_orm)

        # Verify FileCounts created from empty dict
        assert result.file_counts.total == 0
        assert result.file_counts.completed == 0

    def test_from_orm_with_partial_file_counts(self) -> None:
        """VectorStoreResponse.from_orm_model handles partial file_counts data."""
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        # Mock ORM object
        mock_orm = MagicMock()
        mock_orm.id = uuid.uuid4()
        mock_orm.name = "Test Store"
        mock_orm.status = "active"
        mock_orm.created_at = datetime.now(timezone.utc)
        mock_orm.updated_at = datetime.now(timezone.utc)
        mock_orm.expires_at = None
        mock_orm.metadata_ = {}

        # Partial file counts (missing some fields)
        mock_orm.file_counts = {
            "total": 10,
            "completed": 8,
            # missing in_progress and failed
        }

        result = VectorStoreResponse.from_orm_model(mock_orm)

        # Verify FileCounts created with defaults for missing fields
        assert result.file_counts.total == 10
        assert result.file_counts.completed == 8
        assert result.file_counts.in_progress == 0  # default
        assert result.file_counts.failed == 0  # default

    def test_from_orm_with_complete_file_counts(self) -> None:
        """VectorStoreResponse.from_orm_model handles complete file_counts data."""
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        # Mock ORM object
        mock_orm = MagicMock()
        mock_orm.id = uuid.uuid4()
        mock_orm.name = "Test Store"
        mock_orm.status = "active"
        mock_orm.created_at = datetime.now(timezone.utc)
        mock_orm.updated_at = datetime.now(timezone.utc)
        mock_orm.expires_at = None
        mock_orm.metadata_ = {}

        # Complete file counts
        mock_orm.file_counts = {
            "total": 100,
            "completed": 95,
            "in_progress": 3,
            "failed": 2,
        }

        result = VectorStoreResponse.from_orm_model(mock_orm)

        # Verify all counts are correct
        assert result.file_counts.total == 100
        assert result.file_counts.completed == 95
        assert result.file_counts.in_progress == 3
        assert result.file_counts.failed == 2


class TestFileCountsSchema:
    """Tests for FileCounts schema."""

    def test_file_counts_defaults(self) -> None:
        """FileCounts has correct default values."""
        from maia_vectordb.schemas.vector_store import FileCounts

        counts = FileCounts()

        assert counts.total == 0
        assert counts.completed == 0
        assert counts.in_progress == 0
        assert counts.failed == 0

    def test_file_counts_from_dict(self) -> None:
        """FileCounts can be created from dict with unpacking."""
        from maia_vectordb.schemas.vector_store import FileCounts

        data = {
            "total": 50,
            "completed": 40,
            "in_progress": 5,
            "failed": 5,
        }

        counts = FileCounts(**data)

        assert counts.total == 50
        assert counts.completed == 40
        assert counts.in_progress == 5
        assert counts.failed == 5


class TestSearchSchemaValidation:
    """Tests for search schema validation."""

    def test_search_request_with_negative_max_results(self) -> None:
        """SearchRequest rejects negative max_results."""
        from pydantic import ValidationError

        from maia_vectordb.schemas.search import SearchRequest

        with pytest.raises(ValidationError):
            SearchRequest(
                query="test query",
                max_results=-1,  # Invalid
            )

    def test_search_request_with_zero_max_results(self) -> None:
        """SearchRequest rejects zero max_results."""
        from pydantic import ValidationError

        from maia_vectordb.schemas.search import SearchRequest

        with pytest.raises(ValidationError):
            SearchRequest(
                query="test query",
                max_results=0,  # Invalid
            )

    def test_search_request_with_invalid_score_threshold(self) -> None:
        """SearchRequest validates score_threshold range."""
        from pydantic import ValidationError

        from maia_vectordb.schemas.search import SearchRequest

        # Test > 1.0
        with pytest.raises(ValidationError):
            SearchRequest(
                query="test query",
                score_threshold=1.5,  # Invalid
            )

        # Test < 0.0
        with pytest.raises(ValidationError):
            SearchRequest(
                query="test query",
                score_threshold=-0.1,  # Invalid
            )

    def test_search_request_valid_score_threshold_boundaries(self) -> None:
        """SearchRequest accepts valid score_threshold boundary values."""
        from maia_vectordb.schemas.search import SearchRequest

        # Test 1.0 (valid upper boundary)
        req2 = SearchRequest(query="test", score_threshold=1.0)
        assert req2.score_threshold == 1.0

        # Test 0.0 (valid lower boundary)
        req3 = SearchRequest(query="test", score_threshold=0.0)
        assert req3.score_threshold == 0.0

        # Test 0.5 (valid middle)
        req4 = SearchRequest(query="test", score_threshold=0.5)
        assert req4.score_threshold == 0.5


class TestFileSchemaEdgeCases:
    """Edge case tests for file schemas."""

    def test_file_upload_response_from_orm_with_zero_chunks(self) -> None:
        """FileUploadResponse.from_orm_model handles zero chunks."""
        from maia_vectordb.models.file import FileStatus
        from maia_vectordb.schemas.file import FileUploadResponse

        mock_file = MagicMock()
        mock_file.id = uuid.uuid4()
        mock_file.vector_store_id = uuid.uuid4()
        mock_file.filename = "test.txt"
        mock_file.status = FileStatus.in_progress
        mock_file.bytes = 1000
        mock_file.purpose = "assistants"
        mock_file.created_at = datetime.now(timezone.utc)

        result = FileUploadResponse.from_orm_model(mock_file, chunk_count=0)

        assert result.id == str(mock_file.id)
        assert result.status == "in_progress"
        assert result.bytes == 1000
        assert result.chunk_count == 0

    def test_file_upload_response_from_orm_with_large_chunk_count(self) -> None:
        """FileUploadResponse.from_orm_model handles large chunk counts."""
        from maia_vectordb.models.file import FileStatus
        from maia_vectordb.schemas.file import FileUploadResponse

        mock_file = MagicMock()
        mock_file.id = uuid.uuid4()
        mock_file.vector_store_id = uuid.uuid4()
        mock_file.filename = "large.txt"
        mock_file.status = FileStatus.completed
        mock_file.bytes = 10_000_000
        mock_file.purpose = "assistants"
        mock_file.created_at = datetime.now(timezone.utc)

        result = FileUploadResponse.from_orm_model(mock_file, chunk_count=10000)

        assert result.id == str(mock_file.id)
        assert result.status == "completed"
        assert result.bytes == 10_000_000
        assert result.chunk_count == 10000

    def test_file_upload_response_from_orm_all_status_values(self) -> None:
        """FileUploadResponse.from_orm_model handles all FileStatus enum values."""
        from maia_vectordb.models.file import FileStatus
        from maia_vectordb.schemas.file import FileUploadResponse

        statuses = [
            FileStatus.in_progress,
            FileStatus.completed,
            FileStatus.cancelled,
            FileStatus.failed,
        ]

        for status in statuses:
            mock_file = MagicMock()
            mock_file.id = uuid.uuid4()
            mock_file.vector_store_id = uuid.uuid4()
            mock_file.filename = f"test-{status.value}.txt"
            mock_file.status = status
            mock_file.bytes = 100
            mock_file.purpose = "assistants"
            mock_file.created_at = datetime.now(timezone.utc)

            result = FileUploadResponse.from_orm_model(mock_file)

            assert result.status == status.value


class TestVectorStoreStatusEnum:
    """Tests for VectorStore status enum handling."""

    def test_vector_store_response_from_orm_all_status_values(self) -> None:
        """VectorStoreResponse.from_orm_model handles all status enum values."""
        from maia_vectordb.models.vector_store import VectorStoreStatus
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        statuses = [
            VectorStoreStatus.expired,
            VectorStoreStatus.in_progress,
            VectorStoreStatus.completed,
        ]

        for status in statuses:
            mock_orm = MagicMock()
            mock_orm.id = uuid.uuid4()
            mock_orm.name = f"Test Store - {status.value}"
            mock_orm.status = status
            mock_orm.file_counts = None
            mock_orm.metadata_ = None
            mock_orm.created_at = datetime.now(timezone.utc)
            mock_orm.updated_at = datetime.now(timezone.utc)
            mock_orm.expires_at = None

            result = VectorStoreResponse.from_orm_model(mock_orm)

            assert result.status == status.value

    def test_vector_store_response_from_orm_with_expires_at_present(self) -> None:
        """VectorStoreResponse.from_orm_model handles expires_at when present."""
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        expires_dt = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        mock_orm = MagicMock()
        mock_orm.id = uuid.uuid4()
        mock_orm.name = "Expiring Store"
        mock_orm.status = "completed"
        mock_orm.file_counts = None
        mock_orm.metadata_ = None
        mock_orm.created_at = datetime.now(timezone.utc)
        mock_orm.updated_at = datetime.now(timezone.utc)
        mock_orm.expires_at = expires_dt

        result = VectorStoreResponse.from_orm_model(mock_orm)

        assert result.expires_at == int(expires_dt.timestamp())
        assert isinstance(result.expires_at, int)

    def test_vector_store_response_from_orm_with_none_metadata(self) -> None:
        """VectorStoreResponse.from_orm_model handles None metadata."""
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        mock_orm = MagicMock()
        mock_orm.id = uuid.uuid4()
        mock_orm.name = "No Metadata Store"
        mock_orm.status = "completed"
        mock_orm.file_counts = None
        mock_orm.metadata_ = None
        mock_orm.created_at = datetime.now(timezone.utc)
        mock_orm.updated_at = datetime.now(timezone.utc)
        mock_orm.expires_at = None

        result = VectorStoreResponse.from_orm_model(mock_orm)

        assert result.metadata is None


class TestListResponsePagination:
    """Tests for list response schemas with various data states."""

    def test_vector_store_list_response_with_empty_data(self) -> None:
        """VectorStoreListResponse handles empty data list."""
        from maia_vectordb.schemas.vector_store import VectorStoreListResponse

        response = VectorStoreListResponse(data=[])

        assert response.object == "list"
        assert response.data == []
        assert response.first_id is None
        assert response.last_id is None
        assert response.has_more is False

    def test_vector_store_list_response_with_single_item(self) -> None:
        """VectorStoreListResponse handles single item."""
        from maia_vectordb.schemas.vector_store import (
            VectorStoreListResponse,
            VectorStoreResponse,
        )

        store = VectorStoreResponse(
            id="vs-123",
            name="Single Store",
            status="completed",
            created_at=1700000000,
            updated_at=1700000060,
        )

        response = VectorStoreListResponse(
            data=[store],
            first_id="vs-123",
            last_id="vs-123",
            has_more=False,
        )

        assert response.object == "list"
        assert len(response.data) == 1
        assert response.first_id == "vs-123"
        assert response.last_id == "vs-123"
        assert response.has_more is False

    def test_vector_store_list_response_with_max_pagination(self) -> None:
        """VectorStoreListResponse handles maximum pagination scenario."""
        from maia_vectordb.schemas.vector_store import (
            VectorStoreListResponse,
            VectorStoreResponse,
        )

        # Create 100 stores (max typical page size)
        stores = [
            VectorStoreResponse(
                id=f"vs-{i:03d}",
                name=f"Store {i}",
                status="completed",
                created_at=1700000000 + i,
                updated_at=1700000060 + i,
            )
            for i in range(100)
        ]

        response = VectorStoreListResponse(
            data=stores,
            first_id="vs-000",
            last_id="vs-099",
            has_more=True,
        )

        assert response.object == "list"
        assert len(response.data) == 100
        assert response.first_id == "vs-000"
        assert response.last_id == "vs-099"
        assert response.has_more is True

    def test_file_list_response_with_empty_data(self) -> None:
        """FileListResponse handles empty data list."""
        from maia_vectordb.schemas.file import FileListResponse

        response = FileListResponse(data=[])

        assert response.object == "list"
        assert response.data == []
        assert response.first_id is None
        assert response.last_id is None
        assert response.has_more is False

    def test_file_list_response_with_single_item(self) -> None:
        """FileListResponse handles single item."""
        from maia_vectordb.schemas.file import FileListResponse, FileUploadResponse

        file_resp = FileUploadResponse(
            id="file-123",
            vector_store_id="vs-123",
            filename="test.txt",
            status="completed",
            created_at=1700000000,
        )

        response = FileListResponse(
            data=[file_resp],
            first_id="file-123",
            last_id="file-123",
            has_more=False,
        )

        assert response.object == "list"
        assert len(response.data) == 1
        assert response.first_id == "file-123"
        assert response.last_id == "file-123"
        assert response.has_more is False

    def test_file_list_response_with_max_pagination(self) -> None:
        """FileListResponse handles maximum pagination scenario."""
        from maia_vectordb.schemas.file import FileListResponse, FileUploadResponse

        # Create 100 files (max typical page size)
        files = [
            FileUploadResponse(
                id=f"file-{i:03d}",
                vector_store_id="vs-123",
                filename=f"file-{i}.txt",
                status="completed",
                created_at=1700000000 + i,
            )
            for i in range(100)
        ]

        response = FileListResponse(
            data=files,
            first_id="file-000",
            last_id="file-099",
            has_more=True,
        )

        assert response.object == "list"
        assert len(response.data) == 100
        assert response.first_id == "file-000"
        assert response.last_id == "file-099"
        assert response.has_more is True


class TestSearchRequestValidationBoundaries:
    """Tests for SearchRequest validation boundaries."""

    def test_search_request_max_results_minimum_boundary(self) -> None:
        """SearchRequest accepts max_results=1 (minimum valid)."""
        from maia_vectordb.schemas.search import SearchRequest

        req = SearchRequest(query="test", max_results=1)

        assert req.max_results == 1

    def test_search_request_max_results_maximum_boundary(self) -> None:
        """SearchRequest accepts max_results=100 (maximum valid)."""
        from maia_vectordb.schemas.search import SearchRequest

        req = SearchRequest(query="test", max_results=100)

        assert req.max_results == 100

    def test_search_request_max_results_exceeds_maximum(self) -> None:
        """SearchRequest rejects max_results=101 (exceeds maximum)."""
        from pydantic import ValidationError

        from maia_vectordb.schemas.search import SearchRequest

        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query="test", max_results=101)

        assert "max_results" in str(exc_info.value)


class TestModelConfigFromAttributes:
    """Tests verifying model_config includes from_attributes=True."""

    def test_file_counts_has_from_attributes(self) -> None:
        """FileCounts model_config has from_attributes=True."""
        from maia_vectordb.schemas.vector_store import FileCounts

        assert FileCounts.model_config.get("from_attributes") is True

    def test_create_vector_store_request_has_from_attributes(self) -> None:
        """CreateVectorStoreRequest model_config has from_attributes=True."""
        from maia_vectordb.schemas.vector_store import CreateVectorStoreRequest

        assert CreateVectorStoreRequest.model_config.get("from_attributes") is True

    def test_vector_store_response_has_from_attributes(self) -> None:
        """VectorStoreResponse model_config has from_attributes=True."""
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        assert VectorStoreResponse.model_config.get("from_attributes") is True

    def test_vector_store_list_response_has_from_attributes(self) -> None:
        """VectorStoreListResponse model_config has from_attributes=True."""
        from maia_vectordb.schemas.vector_store import VectorStoreListResponse

        assert VectorStoreListResponse.model_config.get("from_attributes") is True

    def test_delete_vector_store_response_has_from_attributes(self) -> None:
        """DeleteVectorStoreResponse model_config has from_attributes=True."""
        from maia_vectordb.schemas.vector_store import DeleteVectorStoreResponse

        assert DeleteVectorStoreResponse.model_config.get("from_attributes") is True

    def test_file_upload_response_has_from_attributes(self) -> None:
        """FileUploadResponse model_config has from_attributes=True."""
        from maia_vectordb.schemas.file import FileUploadResponse

        assert FileUploadResponse.model_config.get("from_attributes") is True

    def test_file_list_response_has_from_attributes(self) -> None:
        """FileListResponse model_config has from_attributes=True."""
        from maia_vectordb.schemas.file import FileListResponse

        assert FileListResponse.model_config.get("from_attributes") is True

    def test_search_request_has_from_attributes(self) -> None:
        """SearchRequest model_config has from_attributes=True."""
        from maia_vectordb.schemas.search import SearchRequest

        assert SearchRequest.model_config.get("from_attributes") is True

    def test_search_result_has_from_attributes(self) -> None:
        """SearchResult model_config has from_attributes=True."""
        from maia_vectordb.schemas.search import SearchResult

        assert SearchResult.model_config.get("from_attributes") is True

    def test_search_response_has_from_attributes(self) -> None:
        """SearchResponse model_config has from_attributes=True."""
        from maia_vectordb.schemas.search import SearchResponse

        assert SearchResponse.model_config.get("from_attributes") is True


class TestOpenAIObjectTypeDefaults:
    """Tests verifying OpenAI object type string defaults."""

    def test_vector_store_response_object_default(self) -> None:
        """VectorStoreResponse has correct object default."""
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        response = VectorStoreResponse(
            id="vs-123",
            name="Test",
            status="completed",
            created_at=1700000000,
            updated_at=1700000060,
        )

        assert response.object == "vector_store"

    def test_vector_store_list_response_object_default(self) -> None:
        """VectorStoreListResponse has correct object default."""
        from maia_vectordb.schemas.vector_store import VectorStoreListResponse

        response = VectorStoreListResponse(data=[])

        assert response.object == "list"

    def test_delete_vector_store_response_object_default(self) -> None:
        """DeleteVectorStoreResponse has correct object default."""
        from maia_vectordb.schemas.vector_store import DeleteVectorStoreResponse

        response = DeleteVectorStoreResponse(id="vs-123")

        assert response.object == "vector_store.deleted"

    def test_file_upload_response_object_default(self) -> None:
        """FileUploadResponse has correct object default."""
        from maia_vectordb.schemas.file import FileUploadResponse

        response = FileUploadResponse(
            id="file-123",
            vector_store_id="vs-123",
            filename="test.txt",
            status="completed",
            created_at=1700000000,
        )

        assert response.object == "vector_store.file"

    def test_file_list_response_object_default(self) -> None:
        """FileListResponse has correct object default."""
        from maia_vectordb.schemas.file import FileListResponse

        response = FileListResponse(data=[])

        assert response.object == "list"

    def test_search_response_object_default(self) -> None:
        """SearchResponse has correct object default."""
        from maia_vectordb.schemas.search import SearchResponse

        response = SearchResponse(data=[], search_query="test")

        assert response.object == "list"


class TestTimestampConversion:
    """Tests verifying datetime to int epoch conversion."""

    def test_vector_store_response_timestamp_conversion(self) -> None:
        """VectorStoreResponse converts datetime to int epoch."""
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        updated = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

        mock_orm = MagicMock()
        mock_orm.id = uuid.uuid4()
        mock_orm.name = "Test Store"
        mock_orm.status = "completed"
        mock_orm.file_counts = None
        mock_orm.metadata_ = None
        mock_orm.created_at = created
        mock_orm.updated_at = updated
        mock_orm.expires_at = None

        result = VectorStoreResponse.from_orm_model(mock_orm)

        assert result.created_at == int(created.timestamp())
        assert result.updated_at == int(updated.timestamp())
        assert isinstance(result.created_at, int)
        assert isinstance(result.updated_at, int)

    def test_file_upload_response_timestamp_conversion(self) -> None:
        """FileUploadResponse converts datetime to int epoch."""
        from maia_vectordb.schemas.file import FileUploadResponse

        created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        mock_file = MagicMock()
        mock_file.id = uuid.uuid4()
        mock_file.vector_store_id = uuid.uuid4()
        mock_file.filename = "test.txt"
        mock_file.status = "completed"
        mock_file.bytes = 100
        mock_file.purpose = "assistants"
        mock_file.created_at = created

        result = FileUploadResponse.from_orm_model(mock_file)

        assert result.created_at == int(created.timestamp())
        assert isinstance(result.created_at, int)


class TestJSONSerializationOpenAIFormat:
    """Tests verifying JSON serialization produces OpenAI-compatible field names."""

    def test_vector_store_response_json_no_snake_case_leak(self) -> None:
        """VectorStoreResponse JSON output has no Python snake_case leaks."""
        from maia_vectordb.schemas.vector_store import VectorStoreResponse

        response = VectorStoreResponse(
            id="vs-123",
            name="Test Store",
            status="completed",
            created_at=1700000000,
            updated_at=1700000060,
            metadata={"key": "value"},
        )

        json_dict = response.model_dump()

        # Verify all expected fields are present
        assert "id" in json_dict
        assert "object" in json_dict
        assert "name" in json_dict
        assert "status" in json_dict
        assert "file_counts" in json_dict
        assert "metadata" in json_dict
        assert "created_at" in json_dict
        assert "updated_at" in json_dict
        assert "expires_at" in json_dict

        # Verify no underscore-suffixed fields leak (metadata_ → metadata)
        assert "metadata_" not in json_dict
        assert "file_counts_" not in json_dict

    def test_file_upload_response_json_no_snake_case_leak(self) -> None:
        """FileUploadResponse JSON output has no Python snake_case leaks."""
        from maia_vectordb.schemas.file import FileUploadResponse

        response = FileUploadResponse(
            id="file-123",
            vector_store_id="vs-123",
            filename="test.txt",
            status="completed",
            created_at=1700000000,
        )

        json_dict = response.model_dump()

        # Verify all expected fields are present
        assert "id" in json_dict
        assert "object" in json_dict
        assert "vector_store_id" in json_dict
        assert "filename" in json_dict
        assert "status" in json_dict
        assert "bytes" in json_dict
        assert "chunk_count" in json_dict
        assert "purpose" in json_dict
        assert "created_at" in json_dict

    def test_search_request_json_no_snake_case_leak(self) -> None:
        """SearchRequest JSON output has no Python snake_case leaks."""
        from maia_vectordb.schemas.search import SearchRequest

        request = SearchRequest(
            query="test",
            max_results=10,
            filter={"key": "value"},
            score_threshold=0.7,
        )

        json_dict = request.model_dump()

        # Verify all expected fields are present
        assert "query" in json_dict
        assert "max_results" in json_dict
        assert "filter" in json_dict
        assert "score_threshold" in json_dict
