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
