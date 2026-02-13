"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

import maia_vectordb.models  # noqa: F401  — register all ORM models with Base.metadata
from maia_vectordb.api.files import router as files_router
from maia_vectordb.api.search import router as search_router
from maia_vectordb.api.vector_stores import router as vector_stores_router
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


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
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

# --- Exception handlers (consistent JSON error envelope) ---
register_exception_handlers(app)

# --- Middleware (outermost first) ---
# Starlette processes middleware in reverse-add order so the last-added
# middleware runs first.  We want RequestID before Logging so the log
# line can include the request_id.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(vector_stores_router)
app.include_router(files_router)
app.include_router(search_router)


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
    except Exception as exc:
        db_health = ComponentHealth(status="error", detail=str(exc))

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
