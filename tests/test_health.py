"""Tests for the health check endpoint and OpenAPI documentation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from maia_vectordb.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_ok_when_db_reachable(self) -> None:
        """Returns 200 with status=ok when database is reachable."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("maia_vectordb.main.get_session_factory", return_value=mock_factory):
            response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["version"] == "0.1.0"
        assert body["database"]["status"] == "ok"
        assert "openai_api_key_set" in body

    def test_health_503_when_db_unreachable(self) -> None:
        """Returns 503 with status=degraded when database is unreachable."""
        with patch(
            "maia_vectordb.main.get_session_factory",
            side_effect=RuntimeError("Database engine not initialised"),
        ):
            response = client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["database"]["status"] == "error"
        assert body["database"]["detail"] == "Database connection failed"

    def test_health_503_when_session_query_fails(self) -> None:
        """Returns 503 when SELECT 1 query fails."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(
            side_effect=ConnectionError("Connection refused")
        )
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("maia_vectordb.main.get_session_factory", return_value=mock_factory):
            response = client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["database"]["status"] == "error"
        assert body["database"]["detail"] == "Database connection failed"

    def test_health_openai_key_flag_true(self) -> None:
        """Reports openai_api_key_set=True when key is configured."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with (
            patch(
                "maia_vectordb.main.get_session_factory",
                return_value=mock_factory,
            ),
            patch("maia_vectordb.main.settings") as mock_settings,
        ):
            mock_settings.openai_api_key = "sk-test-key"
            response = client.get("/health")

        assert response.json()["openai_api_key_set"] is True

    def test_health_openai_key_flag_false(self) -> None:
        """Reports openai_api_key_set=False when key is empty."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with (
            patch(
                "maia_vectordb.main.get_session_factory",
                return_value=mock_factory,
            ),
            patch("maia_vectordb.main.settings") as mock_settings,
        ):
            mock_settings.openai_api_key = ""
            response = client.get("/health")

        assert response.json()["openai_api_key_set"] is False

    def test_health_response_structure(self) -> None:
        """Response contains all expected keys."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("maia_vectordb.main.get_session_factory", return_value=mock_factory):
            response = client.get("/health")

        body = response.json()
        assert set(body.keys()) == {
            "status",
            "version",
            "database",
            "openai_api_key_set",
        }
        assert set(body["database"].keys()) == {"status", "detail"}


class TestOpenAPIDocs:
    """Tests for OpenAPI schema and documentation endpoints."""

    def test_swagger_ui_accessible(self) -> None:
        """Swagger UI renders at /docs."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_accessible(self) -> None:
        """ReDoc renders at /redoc."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_schema_metadata(self) -> None:
        """OpenAPI schema has correct title, description, and version."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "MAIA VectorDB"
        assert "pgvector" in schema["info"]["description"]
        assert schema["info"]["version"] == "0.1.0"

    def test_openapi_tags_present(self) -> None:
        """OpenAPI schema includes tag descriptions for all groups."""
        response = client.get("/openapi.json")
        schema = response.json()
        tag_names = [t["name"] for t in schema["tags"]]
        assert "health" in tag_names
        assert "vector_stores" in tag_names
        assert "files" in tag_names
        assert "search" in tag_names

    def test_openapi_all_endpoints_present(self) -> None:
        """All API endpoints appear in the OpenAPI schema."""
        response = client.get("/openapi.json")
        paths = response.json()["paths"]
        assert "/health" in paths
        assert "/v1/vector_stores" in paths
        assert "/v1/vector_stores/{vector_store_id}" in paths
        assert "/v1/vector_stores/{vector_store_id}/files" in paths
        assert "/v1/vector_stores/{vector_store_id}/search" in paths

    def test_openapi_schema_has_examples(self) -> None:
        """Schemas in OpenAPI spec include examples from json_schema_extra."""
        response = client.get("/openapi.json")
        schemas = response.json()["components"]["schemas"]

        # Verify key schemas have examples
        for schema_name in [
            "CreateVectorStoreRequest",
            "VectorStoreResponse",
            "SearchRequest",
            "SearchResult",
            "HealthResponse",
        ]:
            assert schema_name in schemas, f"Missing schema: {schema_name}"
            assert "examples" in schemas[schema_name], (
                f"Schema {schema_name} missing examples"
            )
