"""Tests for embedding client initialization and edge cases."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


class TestEmbeddingClientCreation:
    """Tests for _get_client function."""

    @patch("maia_vectordb.services.embedding.settings")
    def test_get_client_creates_openai_client(self, mock_settings: MagicMock) -> None:
        """_get_client creates AsyncOpenAI client with correct API key."""
        from maia_vectordb.services.embedding import _get_client

        mock_settings.openai_api_key = "test-api-key-123"

        _patch = "maia_vectordb.services.embedding.openai.AsyncOpenAI"
        with patch(_patch) as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            result = _get_client()

            # Verify client created with correct key
            mock_openai.assert_called_once_with(api_key="test-api-key-123")
            assert result == mock_client

    @patch("maia_vectordb.services.embedding.settings")
    def test_get_client_uses_settings_api_key(self, mock_settings: MagicMock) -> None:
        """_get_client uses API key from settings."""
        from maia_vectordb.services.embedding import _get_client

        test_key = "sk-test-key-from-settings"
        mock_settings.openai_api_key = test_key

        _patch = "maia_vectordb.services.embedding.openai.AsyncOpenAI"
        with patch(_patch) as mock_openai:
            _get_client()

            # Verify the key from settings was used
            call_kwargs = mock_openai.call_args.kwargs
            assert call_kwargs["api_key"] == test_key


class TestEmbedTextsEdgeCases:
    """Additional edge case tests for embed_texts."""

    @patch("maia_vectordb.services.embedding._get_client")
    @patch("maia_vectordb.services.embedding.settings")
    async def test_embed_texts_uses_default_model(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """embed_texts uses default model from settings when not specified."""
        from maia_vectordb.services.embedding import embed_texts

        mock_settings.embedding_model = "text-embedding-3-small"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(index=0, embedding=[0.1, 0.2, 0.3]),
        ]
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        # Call without model parameter
        result = await embed_texts(["test text"])

        # Verify default model was used
        call_kwargs = mock_client.embeddings.create.call_args.kwargs
        assert call_kwargs["model"] == "text-embedding-3-small"
        assert len(result) == 1

    @patch("maia_vectordb.services.embedding._get_client")
    async def test_embed_texts_custom_model_overrides_default(
        self, mock_get_client: MagicMock
    ) -> None:
        """embed_texts uses custom model when provided."""
        from maia_vectordb.services.embedding import embed_texts

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(index=0, embedding=[0.1, 0.2]),
        ]
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        # Call with custom model
        await embed_texts(["test"], model="text-embedding-3-large")

        # Verify custom model was used
        call_kwargs = mock_client.embeddings.create.call_args.kwargs
        assert call_kwargs["model"] == "text-embedding-3-large"

    @patch("maia_vectordb.services.embedding._get_client")
    @patch("maia_vectordb.services.embedding.settings")
    async def test_embed_texts_maintains_order_across_batches(
        self, mock_settings: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """embed_texts maintains correct order when processing multiple batches."""
        from maia_vectordb.services.embedding import embed_texts

        mock_settings.embedding_model = "text-embedding-3-small"

        # Create input that requires multiple batches
        texts = [f"text_{i}" for i in range(5)]

        mock_client = MagicMock()

        # Mock responses for each batch - return out of order to test sorting
        def create_response(batch_texts: list[str]) -> MagicMock:
            response = MagicMock()
            # Return embeddings in reverse order to test sorting
            response.data = [
                MagicMock(index=len(batch_texts) - 1 - i, embedding=[float(i)])
                for i in range(len(batch_texts))
            ]
            return response

        mock_client.embeddings.create = AsyncMock(
            side_effect=lambda input, model, **kwargs: create_response(input)
        )
        mock_get_client.return_value = mock_client

        with patch("maia_vectordb.services.embedding._MAX_BATCH_SIZE", 2):
            result = await embed_texts(texts)

        # Verify order is maintained
        assert len(result) == 5
        # Each embedding should be sorted correctly despite batch boundaries
