"""Tests for background file processing functionality."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.api.files import _process_file_background
from maia_vectordb.models.file import File, FileStatus


class TestBackgroundProcessing:
    """Tests for background file processing."""

    @pytest.mark.asyncio
    @patch("maia_vectordb.api.files.get_session_factory")
    @patch("maia_vectordb.api.files._process_chunks")
    async def test_background_success_updates_file_status(
        self,
        mock_process_chunks: MagicMock,
        mock_factory: MagicMock,
    ) -> None:
        """Background processing marks file as completed on success."""
        # Setup
        file_id = uuid.uuid4()
        store_id = uuid.uuid4()
        test_text = "Test content for background processing"

        # Mock chunks
        mock_chunk = MagicMock()
        mock_process_chunks.return_value = [mock_chunk]

        # Mock session and file
        mock_file = MagicMock(spec=File)
        mock_file.status = FileStatus.in_progress

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_file)
        mock_session.commit = AsyncMock()
        mock_session.add_all = MagicMock()

        mock_factory.return_value = MagicMock(return_value=mock_session)

        # Execute
        await _process_file_background(file_id, store_id, test_text)

        # Verify
        mock_process_chunks.assert_called_once_with(test_text, file_id, store_id)
        mock_session.add_all.assert_called_once()
        assert mock_file.status == FileStatus.completed
        assert mock_session.commit.call_count == 1

    @pytest.mark.asyncio
    @patch("maia_vectordb.api.files.get_session_factory")
    @patch("maia_vectordb.api.files._process_chunks")
    async def test_background_exception_marks_file_failed(
        self,
        mock_process_chunks: MagicMock,
        mock_factory: MagicMock,
    ) -> None:
        """Background processing marks file as failed on exception."""
        # Setup
        file_id = uuid.uuid4()
        store_id = uuid.uuid4()
        test_text = "Test content that will fail"

        # Mock chunks to raise an error
        mock_process_chunks.side_effect = RuntimeError("Embedding service failed")

        # Mock session and file
        mock_file = MagicMock(spec=File)
        mock_file.status = FileStatus.in_progress

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_file)
        mock_session.commit = AsyncMock()

        mock_factory.return_value = MagicMock(return_value=mock_session)

        # Execute - should not raise
        await _process_file_background(file_id, store_id, test_text)

        # Verify file marked as failed
        assert mock_file.status == FileStatus.failed
        assert mock_session.commit.call_count == 1

    @pytest.mark.asyncio
    @patch("maia_vectordb.api.files.get_session_factory")
    @patch("maia_vectordb.api.files._process_chunks")
    async def test_background_handles_missing_file(
        self,
        mock_process_chunks: MagicMock,
        mock_factory: MagicMock,
    ) -> None:
        """Background processing handles case where file is deleted."""
        # Setup
        file_id = uuid.uuid4()
        store_id = uuid.uuid4()
        test_text = "Test content"

        mock_process_chunks.return_value = []

        # Mock session with None file (deleted)
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        mock_session.add_all = MagicMock()

        mock_factory.return_value = MagicMock(return_value=mock_session)

        # Execute - should not raise
        await _process_file_background(file_id, store_id, test_text)

        # Verify commits still happen
        assert mock_session.commit.call_count == 1

    @pytest.mark.asyncio
    @patch("maia_vectordb.api.files.get_session_factory")
    @patch("maia_vectordb.api.files._process_chunks")
    async def test_background_exception_with_missing_file(
        self,
        mock_process_chunks: MagicMock,
        mock_factory: MagicMock,
    ) -> None:
        """Background processing handles exception when file is missing."""
        # Setup
        file_id = uuid.uuid4()
        store_id = uuid.uuid4()
        test_text = "Test content"

        # First call succeeds (success path), second call returns None (error path)
        mock_process_chunks.side_effect = RuntimeError("Test error")

        # Mock session with None file in error handler
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()

        mock_factory.return_value = MagicMock(return_value=mock_session)

        # Execute - should not raise
        await _process_file_background(file_id, store_id, test_text)

        # Verify commit still happens even with missing file
        assert mock_session.commit.call_count == 1

    @pytest.mark.asyncio
    @patch("maia_vectordb.api.files.get_session_factory")
    @patch("maia_vectordb.api.files._process_chunks")
    async def test_background_empty_chunks_still_completes(
        self,
        mock_process_chunks: MagicMock,
        mock_factory: MagicMock,
    ) -> None:
        """Background processing completes even with empty chunks."""
        # Setup
        file_id = uuid.uuid4()
        store_id = uuid.uuid4()
        test_text = ""

        # Mock empty chunks
        mock_process_chunks.return_value = []

        # Mock session and file
        mock_file = MagicMock(spec=File)
        mock_file.status = FileStatus.in_progress

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = AsyncMock(return_value=mock_file)
        mock_session.commit = AsyncMock()
        mock_session.add_all = MagicMock()

        mock_factory.return_value = MagicMock(return_value=mock_session)

        # Execute
        await _process_file_background(file_id, store_id, test_text)

        # Verify file marked as completed even with no chunks
        assert mock_file.status == FileStatus.completed
        mock_session.add_all.assert_called_once_with([])
