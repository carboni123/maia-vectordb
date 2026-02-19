"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import text

import maia_vectordb.models  # noqa: F401  — register all ORM models with Base.metadata
from maia_vectordb.api.files import router as files_router
from maia_vectordb.api.search import router as search_router
from maia_vectordb.api.vector_stores import router as vector_stores_router
from maia_vectordb.core.auth import verify_api_key
from maia_vectordb.core.config import settings
from maia_vectordb.core.handlers import register_exception_handlers
from maia_vectordb.core.logging_config import setup_logging
from maia_vectordb.core.middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
)
from maia_vectordb.db.engine import dispose_engine, get_session_factory, init_engine
from maia_vectordb.schemas.health import ComponentHealth, HealthResponse

# Configure structured logging at import time
setup_logging()

# --- OpenAPI tag metadata ---
TAG_METADATA = [
    {
        "name": "health",
        "description": "Service health checks and status monitoring.",
    },
    {
        "name": "vector_stores",
        "description": "Create, list, retrieve, and delete vector stores.",
    },
    {
        "name": "files",
        "description": "Upload documents and check processing status.",
    },
    {
        "name": "search",
        "description": "Similarity search over vector store embeddings.",
    },
]

# --- Rate limiter ---
# Created at module level so it is available when the app processes requests.
# default_limits applies to every route that does not have its own @limiter.limit
# or @limiter.exempt decorator.
_limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
)

# --- Prometheus instrumentator ---
# Calling instrument() without add() activates the default metric set which
# includes both http_request_duration_seconds and http_requests_total.
_instrumentator = Instrumentator()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    if not settings.api_keys:
        raise ValueError(
            "API_KEYS must be configured before starting the server. "
            "Set the API_KEYS environment variable to a comma-separated list of keys."
        )
    await init_engine()
    yield
    await dispose_engine()


app = FastAPI(
    title="MAIA VectorDB",
    description=(
        "OpenAI-compatible vector store API service powered by PostgreSQL "
        "and pgvector. Provides endpoints for creating vector stores, "
        "uploading documents with automatic chunking and embedding, "
        "and performing similarity search."
    ),
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=TAG_METADATA,
)

# Attach limiter to app state so SlowAPIMiddleware can find it.
app.state.limiter = _limiter

# --- Exception handlers (consistent JSON error envelope) ---
register_exception_handlers(app)


def _rate_limit_exceeded_handler(
    _request: Request,
    _exc: Exception,
) -> JSONResponse:
    """Return 429 with the standard error envelope on rate limit violations.

    Must be a regular (non-async) function: SlowAPIMiddleware calls it
    synchronously inside its dispatch loop and falls back to the built-in
    handler when the registered handler is a coroutine function.
    """
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "message": "Rate limit exceeded. Please slow down.",
                "type": "rate_limit_exceeded",
                "code": 429,
            }
        },
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Instrument app for Prometheus metrics (adds middleware that records every request).
# The default instrumentation provides http_request_duration_seconds (histogram)
# and http_requests_total (counter).
_instrumentator.instrument(app)

# --- Middleware (last-added runs first per Starlette reversal) ---
# Stack execution order: RequestID -> Logging -> CORS -> SlowAPI -> route handler
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)


# All v1 routes require a valid X-API-Key header.
_auth = [Depends(verify_api_key)]

app.include_router(vector_stores_router, dependencies=_auth)
app.include_router(files_router, dependencies=_auth)
app.include_router(search_router, dependencies=_auth)

# Expose Prometheus metrics endpoint (no auth — intended for internal scraping).
_instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Service health check",
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is degraded (database unreachable)"},
    },
)
async def health() -> JSONResponse:
    """Check service health including database connectivity and configuration.

    Returns 200 when all components are healthy, or 503 when the database
    is unreachable.
    """
    # Check database connectivity
    db_health = ComponentHealth(status="ok")
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_health = ComponentHealth(status="error", detail="Database connection failed")

    # Check OpenAI API key presence
    openai_key_set = bool(settings.openai_api_key)

    overall = "ok" if db_health.status == "ok" else "degraded"
    status_code = 200 if db_health.status == "ok" else 503

    body = HealthResponse(
        status=overall,
        version="0.1.0",
        database=db_health,
        openai_api_key_set=openai_key_set,
    )

    return JSONResponse(content=body.model_dump(), status_code=status_code)
