"""Tests for rate limiting (AC1, AC3) and Prometheus metrics (AC2, AC4)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from maia_vectordb.main import _rate_limit_exceeded_handler

# ---------------------------------------------------------------------------
# AC1 — 429 responses use the standard error envelope
# ---------------------------------------------------------------------------


class TestRateLimitExceededHandler:
    """Unit tests for the custom RateLimitExceeded exception handler."""

    def test_returns_429_status_code(self) -> None:
        """Handler must return HTTP 429."""
        from slowapi.errors import RateLimitExceeded

        mock_request = MagicMock()
        mock_exc = MagicMock(spec=RateLimitExceeded)

        response = _rate_limit_exceeded_handler(mock_request, mock_exc)

        assert response.status_code == 429

    def test_body_uses_standard_error_envelope(self) -> None:
        """Response body must use the {"error": {...}} envelope."""
        from slowapi.errors import RateLimitExceeded

        mock_request = MagicMock()
        mock_exc = MagicMock(spec=RateLimitExceeded)

        response = _rate_limit_exceeded_handler(mock_request, mock_exc)
        body = json.loads(response.body)

        assert "error" in body
        assert body["error"]["code"] == 429
        assert body["error"]["type"] == "rate_limit_exceeded"
        assert isinstance(body["error"]["message"], str)
        assert body["error"]["message"]  # must be non-empty

    def test_handler_is_not_async(self) -> None:
        """Handler must be sync so SlowAPIMiddleware can call it directly.

        SlowAPIMiddleware uses sync_check_limits() and falls back to its own
        built-in handler when the registered handler is a coroutine function.
        """
        import inspect

        assert not inspect.iscoroutinefunction(_rate_limit_exceeded_handler)

    def test_429_via_http_uses_standard_envelope(self, client: TestClient) -> None:
        """End-to-end: hitting the rate limit must return the standard envelope.

        We temporarily override the limiter with a 1/minute limit and send
        two requests so the second one is rejected.
        """
        from slowapi import Limiter
        from slowapi.util import get_remote_address

        from maia_vectordb.main import app

        original_limiter = app.state.limiter
        try:
            app.state.limiter = Limiter(
                key_func=get_remote_address,
                default_limits=["1/minute"],
            )
            # First request succeeds (401 because no API key, but not rate-limited)
            r1 = client.get("/v1/vector_stores")
            assert r1.status_code != 429

            # Second request is rate-limited (same IP within the window)
            r2 = client.get("/v1/vector_stores")
            assert r2.status_code == 429
            body = r2.json()
            assert body["error"]["code"] == 429
            assert body["error"]["type"] == "rate_limit_exceeded"
        finally:
            app.state.limiter = original_limiter


# ---------------------------------------------------------------------------
# AC2 & AC4 — /metrics returns valid Prometheus text format with required names
# ---------------------------------------------------------------------------


class TestMetricsEndpoint:
    """Tests for the Prometheus metrics endpoint."""

    def test_metrics_returns_200(self, client: TestClient) -> None:
        """GET /metrics must return HTTP 200."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_content_type_is_plain_text(self, client: TestClient) -> None:
        """Content-Type must be text/plain (Prometheus exposition format)."""
        response = client.get("/metrics")
        assert "text/plain" in response.headers.get("content-type", "")

    def test_metrics_includes_http_request_duration_seconds(
        self, client: TestClient
    ) -> None:
        """AC4: http_request_duration_seconds histogram must be present."""
        # Warm-up: first call to /metrics is itself recorded
        client.get("/metrics")
        response = client.get("/metrics")
        assert "http_request_duration_seconds" in response.text

    def test_metrics_includes_http_requests_total(self, client: TestClient) -> None:
        """AC4: http_requests_total counter must be present."""
        client.get("/metrics")
        response = client.get("/metrics")
        assert "http_requests_total" in response.text

    def test_metrics_body_looks_like_prometheus_exposition(
        self, client: TestClient
    ) -> None:
        """Sanity-check: body contains comment lines (# HELP / # TYPE)."""
        response = client.get("/metrics")
        assert "# HELP" in response.text
        assert "# TYPE" in response.text


# ---------------------------------------------------------------------------
# AC3 — Rate limit values configurable from environment
# ---------------------------------------------------------------------------


class TestRateLimitConfiguration:
    """Tests for the RATE_LIMIT_PER_MINUTE environment variable."""

    def test_default_rate_limit_is_positive_integer(self) -> None:
        """Default rate_limit_per_minute must be a positive integer."""
        from maia_vectordb.core.config import settings as current_settings

        assert isinstance(current_settings.rate_limit_per_minute, int)
        assert current_settings.rate_limit_per_minute > 0

    def test_rate_limit_reads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings must pick up RATE_LIMIT_PER_MINUTE from the environment."""
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "120")

        # Re-instantiate Settings; OPENAI_API_KEY is already set in the env.
        from maia_vectordb.core.config import Settings

        test_settings = Settings()
        assert test_settings.rate_limit_per_minute == 120

    def test_limiter_uses_settings_value(self) -> None:
        """The module-level limiter must use settings.rate_limit_per_minute."""
        from maia_vectordb.core.config import settings as current_settings
        from maia_vectordb.main import _limiter

        # _default_limits is a list of LimitGroup objects; iterate each group
        # to reach the underlying RateLimitItem and check its amount.
        assert len(_limiter._default_limits) > 0
        limit_group = _limiter._default_limits[0]
        limit_obj = next(iter(limit_group))
        assert limit_obj.limit.amount == current_settings.rate_limit_per_minute
