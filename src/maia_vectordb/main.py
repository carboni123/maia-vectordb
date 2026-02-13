"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import maia_vectordb.models  # noqa: F401  — register all ORM models with Base.metadata
from maia_vectordb.api.vector_stores import router as vector_stores_router
from maia_vectordb.db.engine import dispose_engine, init_engine


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(vector_stores_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
