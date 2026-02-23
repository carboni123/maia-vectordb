"""Tests for X-API-Key authentication on v1 routes."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from maia_vectordb.db.engine import get_db_session
from maia_vectordb.main import app

# Must match the key set in conftest.py (settings.api_keys = ["test-key"])
VALID_KEY = "test-key"


@pytest.fixture()
def auth_client(mock_session: MagicMock) -> Generator[TestClient, None, None]:
    """TestClient with DB mocked but *without* overriding verify_api_key.

    Use this fixture to test actual authentication behaviour.
    """

    async def _override_session() -> Any:
        yield mock_session

    app.dependency_overrides[get_db_session] = _override_session
    # Intentionally do NOT add verify_api_key override.
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestApiKeyAuthentication:
    """v1 endpoints must reject requests without a valid X-API-Key header."""

    def test_missing_key_returns_401(self, auth_client: TestClient) -> None:
        """Returns 401 when X-API-Key header is absent."""
        resp = auth_client.get("/v1/vector_stores")
        assert resp.status_code == 401
        assert "API key" in resp.json()["error"]["message"]

    def test_invalid_key_returns_401(self, auth_client: TestClient) -> None:
        """Returns 401 when X-API-Key header contains an unknown key."""
        resp = auth_client.get(
            "/v1/vector_stores",
            headers={"X-API-Key": "not-a-real-key"},
        )
        assert resp.status_code == 401
        assert "API key" in resp.json()["error"]["message"]

    def test_valid_key_passes_auth(
        self, auth_client: TestClient, mock_session: MagicMock
    ) -> None:
        """A request with a valid key is not rejected with 401."""
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = auth_client.get(
            "/v1/vector_stores",
            headers={"X-API-Key": VALID_KEY},
        )
        assert resp.status_code == 200

    def test_auth_applies_to_files_endpoint(self, auth_client: TestClient) -> None:
        """File upload endpoint also rejects missing key."""
        import uuid

        store_id = uuid.uuid4()
        resp = auth_client.get(
            f"/v1/vector_stores/{store_id}/files/some-file-id",
        )
        assert resp.status_code == 401

    def test_auth_applies_to_search_endpoint(self, auth_client: TestClient) -> None:
        """Search endpoint also rejects missing key."""
        import uuid

        store_id = uuid.uuid4()
        resp = auth_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "hello"},
        )
        assert resp.status_code == 401


class TestHealthEndpointNoAuth:
    """GET /health must be accessible without authentication."""

    def test_health_returns_200_without_api_key(self) -> None:
        """Health endpoint returns 200 with no X-API-Key header."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("maia_vectordb.main.get_session_factory", return_value=mock_factory):
            resp = TestClient(app).get("/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
