"""Embedding generation endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from maia_vectordb.services.embedding import embed_texts

router = APIRouter(prefix="/v1", tags=["embeddings"])


class EmbedRequest(BaseModel):
    """Request body for embedding generation."""

    input: list[str] = Field(min_length=1, max_length=64)


class EmbedResponse(BaseModel):
    """Response body with embedding vectors."""

    data: list[list[float]]


@router.post("/embeddings", response_model=EmbedResponse)
async def create_embeddings(body: EmbedRequest) -> EmbedResponse:
    """Generate embeddings for the given input texts."""
    vectors = await embed_texts(body.input)
    return EmbedResponse(data=vectors)
