"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import maia_vectordb.models  # noqa: F401  — register all ORM models with Base.metadata
from maia_vectordb.api.files import router as files_router
from maia_vectordb.api.search import router as search_router
from maia_vectordb.api.vector_stores import router as vector_stores_router
from maia_vectordb.core.handlers import register_exception_handlers
from maia_vectordb.core.logging_config import setup_logging
from maia_vectordb.core.middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
)
from maia_vectordb.db.engine import dispose_engine, init_engine

# Configure structured logging at import time
setup_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    await init_engine()
    yield
    await dispose_engine()


app = FastAPI(
    title="MAIA VectorDB",
    description="OpenAI-compatible vector store API",
    version="0.1.0",
    lifespan=lifespan,
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


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
