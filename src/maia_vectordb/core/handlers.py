"""Global exception handlers returning a consistent JSON error envelope."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from maia_vectordb.core.exceptions import APIError

logger = logging.getLogger(__name__)


def _error_response(
    *, status_code: int, message: str, error_type: str
) -> JSONResponse:
    """Build the standard ``{error: {message, type, code}}`` envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "code": status_code,
            }
        },
    )


async def api_error_handler(
    _request: Request, exc: APIError
) -> JSONResponse:
    """Handle custom APIError subclasses."""
    logger.warning("APIError [%s]: %s", exc.error_type, exc.message)
    return _error_response(
        status_code=exc.status_code,
        message=exc.message,
        error_type=exc.error_type,
    )


async def http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle FastAPI / Starlette HTTPException consistently."""
    detail = (
        exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    )
    return _error_response(
        status_code=exc.status_code,
        message=detail,
        error_type="http_error",
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic / query-param validation errors."""
    messages = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err["loc"])  # noqa: E741
        messages.append(f"{loc}: {err['msg']}")
    combined = "; ".join(messages)
    return _error_response(
        status_code=422,
        message=combined,
        error_type="validation_error",
    )


async def unhandled_exception_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all — never leak stack traces to the client."""
    logger.exception("Unhandled exception: %s", exc)
    return _error_response(
        status_code=500,
        message="Internal server error",
        error_type="internal_error",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire all exception handlers onto the FastAPI application."""
    app.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
