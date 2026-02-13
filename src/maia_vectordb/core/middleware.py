"""Request middleware: logging, request-ID propagation, and correlation."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi.responses import JSONResponse
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request/response.

    If the caller provides ``X-Request-ID`` it is reused; otherwise a
    new UUID4 is generated.  The ID is stored on
    ``request.state.request_id`` so downstream code can include it in
    logs.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception:
            # Let the outer middleware handle it; just re-raise
            raise
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status code, and duration for every request.

    Also acts as the outermost safety net: any unhandled exception that
    escapes ``BaseHTTPMiddleware.call_next`` is caught here and turned
    into a ``500 Internal Server Error`` JSON response so stack traces
    are never leaked to the client.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # Unhandled error — return safe 500 and log it
            logger.exception(
                "Unhandled exception during %s %s",
                request.method,
                request.url.path,
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": "Internal server error",
                        "type": "internal_error",
                        "code": 500,
                    }
                },
            )

        duration_ms = (time.perf_counter() - start) * 1000
        request_id: str = getattr(request.state, "request_id", "-")
        logger.info(
            "%s %s %d %.1fms [request_id=%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
