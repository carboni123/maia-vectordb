"""Tests for middleware edge cases and error handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse


class TestRequestIDMiddleware:
    """Tests for RequestIDMiddleware exception handling."""

    @pytest.mark.asyncio
    async def test_middleware_reraises_exceptions(self) -> None:
        """Middleware re-raises exceptions from call_next."""
        from maia_vectordb.core.middleware import RequestIDMiddleware

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.state = MagicMock()

        # Mock call_next to raise an exception
        async def failing_call_next(request: Request) -> JSONResponse:
            raise RuntimeError("Downstream handler failed")

        middleware = RequestIDMiddleware(app=MagicMock())

        # Should re-raise the exception
        with pytest.raises(RuntimeError, match="Downstream handler failed"):
            await middleware.dispatch(mock_request, failing_call_next)

        # Verify request_id was still set on state
        assert hasattr(mock_request.state, "request_id")

    @pytest.mark.asyncio
    async def test_middleware_uses_provided_request_id(self) -> None:
        """Middleware uses X-Request-ID header if provided."""
        from maia_vectordb.core.middleware import RequestIDMiddleware

        provided_id = "test-request-id-123"

        # Mock request with provided request ID
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get = MagicMock(return_value=provided_id)
        mock_request.state = MagicMock()

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}

        async def mock_call_next(request: Request) -> MagicMock:
            return mock_response

        middleware = RequestIDMiddleware(app=MagicMock())

        # Execute
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Verify provided ID was used
        assert mock_request.state.request_id == provided_id
        assert response.headers["X-Request-ID"] == provided_id

    @pytest.mark.asyncio
    async def test_middleware_exception_before_response(self) -> None:
        """Middleware handles exceptions that occur before getting response."""
        from maia_vectordb.core.middleware import RequestIDMiddleware

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.state = MagicMock()

        # Mock call_next that raises immediately
        async def immediate_failure(request: Request) -> JSONResponse:
            raise ValueError("Invalid request data")

        middleware = RequestIDMiddleware(app=MagicMock())

        # Should propagate the exception
        with pytest.raises(ValueError, match="Invalid request data"):
            await middleware.dispatch(mock_request, immediate_failure)


class TestExceptionHandlers:
    """Tests for global exception handlers."""

    @pytest.mark.asyncio
    async def test_unhandled_exception_logs_error(self) -> None:
        """Unhandled exception handler logs the exception."""
        from maia_vectordb.core.handlers import unhandled_exception_handler

        mock_request = MagicMock(spec=Request)
        test_exception = RuntimeError("Unexpected error")

        with patch("maia_vectordb.core.handlers.logger") as mock_logger:
            response = await unhandled_exception_handler(mock_request, test_exception)

            # Verify logging
            mock_logger.exception.assert_called_once()
            assert "Unhandled exception" in str(mock_logger.exception.call_args)

            # Verify response
            assert response.status_code == 500
            body = (
                response.body
                if isinstance(response.body, bytes)
                else bytes(response.body)
            )
            assert "Internal server error" in body.decode()

    @pytest.mark.asyncio
    async def test_unhandled_exception_no_stack_trace_leak(self) -> None:
        """Unhandled exception handler doesn't leak stack traces."""
        from maia_vectordb.core.handlers import unhandled_exception_handler

        mock_request = MagicMock(spec=Request)
        test_exception = RuntimeError("Database connection lost")

        response = await unhandled_exception_handler(mock_request, test_exception)

        body = (
            response.body
            if isinstance(response.body, bytes)
            else bytes(response.body)
        )
        response_body = body.decode()

        # Should not contain stack trace information
        assert "Traceback" not in response_body
        assert "RuntimeError" not in response_body
        assert "Database connection lost" not in response_body

        # Should contain generic error message
        assert "Internal server error" in response_body
        assert "internal_error" in response_body


class TestRequestLoggingMiddleware:
    """Tests for request logging middleware edge cases."""

    @pytest.mark.asyncio
    async def test_logging_middleware_records_successful_requests(self) -> None:
        """Request logging middleware logs successful requests."""
        from maia_vectordb.core.middleware import RequestLoggingMiddleware

        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/v1/vector_stores"
        mock_request.client.host = "127.0.0.1"
        mock_request.state = MagicMock()
        mock_request.state.request_id = "test-id-123"

        mock_response = MagicMock()
        mock_response.status_code = 201

        async def successful_call_next(request: Request) -> MagicMock:
            return mock_response

        middleware = RequestLoggingMiddleware(app=MagicMock())

        with patch("maia_vectordb.core.middleware.logger") as mock_logger:
            with patch("maia_vectordb.core.middleware.time") as mock_time:
                mock_time.perf_counter.side_effect = [1000.0, 1000.1]  # 100ms elapsed

                response = await middleware.dispatch(mock_request, successful_call_next)

                # Verify request was logged
                assert mock_logger.info.called
                assert response == mock_response
