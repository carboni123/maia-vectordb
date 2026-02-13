"""Tests for global error handling, middleware, and exception hierarchy."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from maia_vectordb.core.exceptions import (
    APIError,
    DatabaseError,
    EmbeddingServiceError,
    NotFoundError,
    ValidationError,
)
from maia_vectordb.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error_shape(body: dict[str, Any]) -> None:
    """Assert the response matches the standard error envelope."""
    assert "error" in body
    err = body["error"]
    assert "message" in err
    assert "type" in err
    assert "code" in err
    assert isinstance(err["code"], int)


def _clean_route(path: str) -> None:
    """Remove a temporary test route from the app."""
    app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != path]


# ===================================================================
# 1. Custom exception classes
# ===================================================================


class TestExceptionHierarchy:
    """All custom exceptions inherit from APIError."""

    def test_api_error_defaults(self) -> None:
        exc = APIError()
        assert exc.status_code == 500
        assert exc.error_type == "api_error"
        assert exc.message == "An unexpected error occurred"

    def test_not_found_error(self) -> None:
        exc = NotFoundError("Thing missing")
        assert exc.status_code == 404
        assert exc.error_type == "not_found"
        assert isinstance(exc, APIError)

    def test_validation_error(self) -> None:
        exc = ValidationError("Bad input")
        assert exc.status_code == 400
        assert exc.error_type == "validation_error"
        assert isinstance(exc, APIError)

    def test_embedding_service_error(self) -> None:
        exc = EmbeddingServiceError()
        assert exc.status_code == 502
        assert exc.error_type == "embedding_service_error"
        assert isinstance(exc, APIError)

    def test_database_error(self) -> None:
        exc = DatabaseError()
        assert exc.status_code == 503
        assert exc.error_type == "database_error"
        assert isinstance(exc, APIError)


# ===================================================================
# 2. Consistent JSON error format from exception handlers
# ===================================================================


class TestErrorFormat:
    """All error responses use {error: {message, type, code}}."""

    def test_404_has_error_envelope(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Existing 404 from HTTPException gets wrapped."""
        mock_session.get = AsyncMock(return_value=None)
        resp = client.get(f"/v1/vector_stores/{uuid.uuid4()}")
        assert resp.status_code == 404
        body = resp.json()
        _error_shape(body)
        assert body["error"]["code"] == 404

    def test_422_validation_error_envelope(self, client: TestClient) -> None:
        """Pydantic validation errors get the envelope."""
        resp = client.get("/v1/vector_stores?order=bad")
        assert resp.status_code == 422
        body = resp.json()
        _error_shape(body)
        assert body["error"]["type"] == "validation_error"

    def test_unhandled_exception_returns_500(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """An unexpected error returns 500 with safe message."""
        mock_session.get = AsyncMock(side_effect=RuntimeError("kaboom"))
        resp = client.get(f"/v1/vector_stores/{uuid.uuid4()}")
        assert resp.status_code == 500
        body = resp.json()
        _error_shape(body)
        # Must NOT leak the actual traceback
        assert "kaboom" not in body["error"]["message"]
        assert body["error"]["message"] == "Internal server error"

    def test_custom_api_error_format(self, client: TestClient) -> None:
        """Verify a route raising APIError gets the envelope."""

        @app.get("/test-custom-error")
        async def _raise_custom() -> None:
            raise NotFoundError("widget not found")

        resp = client.get("/test-custom-error")
        assert resp.status_code == 404
        body = resp.json()
        _error_shape(body)
        assert body["error"]["message"] == "widget not found"
        assert body["error"]["type"] == "not_found"
        assert body["error"]["code"] == 404

        _clean_route("/test-custom-error")


# ===================================================================
# 3. HTTP status codes map correctly
# ===================================================================


class TestStatusCodeMapping:
    """Custom exceptions map to the correct HTTP status codes."""

    def test_not_found_returns_404(self, client: TestClient) -> None:
        @app.get("/test-404")
        async def _r404() -> None:
            raise NotFoundError("nope")

        resp = client.get("/test-404")
        assert resp.status_code == 404
        _clean_route("/test-404")

    def test_validation_returns_400(self, client: TestClient) -> None:
        @app.get("/test-400")
        async def _r400() -> None:
            raise ValidationError("bad")

        resp = client.get("/test-400")
        assert resp.status_code == 400
        _clean_route("/test-400")

    def test_embedding_error_returns_502(self, client: TestClient) -> None:
        @app.get("/test-502")
        async def _r502() -> None:
            raise EmbeddingServiceError("openai down")

        resp = client.get("/test-502")
        assert resp.status_code == 502
        _clean_route("/test-502")

    def test_database_error_returns_503(self, client: TestClient) -> None:
        @app.get("/test-503")
        async def _r503() -> None:
            raise DatabaseError("pg down")

        resp = client.get("/test-503")
        assert resp.status_code == 503
        _clean_route("/test-503")


# ===================================================================
# 4. Request logging middleware
# ===================================================================


class TestRequestLogging:
    """Request logging captures method, path, status, duration."""

    def test_request_logged(
        self,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level("INFO"):
            resp = client.get("/health")
        # Health may return 503 when no real DB is available; we only
        # care that the request was logged with the correct status.
        assert resp.status_code in (200, 503)
        log_line = [
            r for r in caplog.records if "GET" in r.message and "/health" in r.message
        ]
        assert len(log_line) >= 1
        msg = log_line[0].message
        assert "GET" in msg
        assert "/health" in msg
        assert str(resp.status_code) in msg
        assert "ms" in msg

    def test_error_request_logged(
        self,
        client: TestClient,
        mock_session: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_session.get = AsyncMock(return_value=None)
        with caplog.at_level("INFO"):
            resp = client.get(f"/v1/vector_stores/{uuid.uuid4()}")
        assert resp.status_code == 404
        log_line = [
            r
            for r in caplog.records
            if "GET" in r.message and "/v1/vector_stores" in r.message
        ]
        assert len(log_line) >= 1
        assert "404" in log_line[0].message


# ===================================================================
# 5. Request ID middleware
# ===================================================================


class TestRequestID:
    """X-Request-ID propagated through request lifecycle."""

    def test_request_id_generated(self, client: TestClient) -> None:
        """Response includes X-Request-ID when client omits it."""
        resp = client.get("/health")
        assert "x-request-id" in resp.headers
        # Should be a valid UUID
        uuid.UUID(resp.headers["x-request-id"])

    def test_request_id_echoed(self, client: TestClient) -> None:
        """Client-supplied X-Request-ID is echoed back."""
        custom_id = "my-correlation-123"
        resp = client.get(
            "/health",
            headers={"X-Request-ID": custom_id},
        )
        assert resp.headers["x-request-id"] == custom_id

    def test_request_id_in_log(
        self,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The request ID appears in the log line."""
        custom_id = "trace-abc-789"
        with caplog.at_level("INFO"):
            client.get(
                "/health",
                headers={"X-Request-ID": custom_id},
            )
        log_line = [
            r for r in caplog.records if "GET" in r.message and "/health" in r.message
        ]
        assert len(log_line) >= 1
        assert custom_id in log_line[0].message


# ===================================================================
# 6. No stack traces leaked to client
# ===================================================================


class TestNoLeakedStackTraces:
    """No internal details in error responses."""

    def test_unhandled_runtime_error(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        mock_session.get = AsyncMock(side_effect=RuntimeError("secret DB conn string"))
        resp = client.get(f"/v1/vector_stores/{uuid.uuid4()}")
        body = resp.json()
        full_text = str(body)
        assert "secret DB conn string" not in full_text
        assert "Traceback" not in full_text

    def test_unhandled_type_error(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        mock_session.get = AsyncMock(side_effect=TypeError("'NoneType' no attr"))
        resp = client.get(f"/v1/vector_stores/{uuid.uuid4()}")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["message"] == "Internal server error"
        assert "NoneType" not in str(body)
