"""Similarity search endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from maia_vectordb.api.deps import DBSession
from maia_vectordb.schemas.search import (
    SearchMode,
    SearchRequest,
    SearchResponse,
)
from maia_vectordb.services import search_service, vector_store_service
from maia_vectordb.services.embedding import embed_texts
from maia_vectordb.services.hybrid_search import hybrid_search

router = APIRouter(
    prefix="/v1/vector_stores/{vector_store_id}",
    tags=["search"],
)


@router.post("/search", response_model=SearchResponse)
async def search(
    vector_store_id: uuid.UUID,
    body: SearchRequest,
    session: DBSession,
) -> SearchResponse:
    """Search a vector store using vector similarity or hybrid ranking.

    When ``search_mode`` is ``"vector"`` (default), performs pure cosine
    similarity search via pgvector.

    When ``search_mode`` is ``"hybrid"``, combines vector similarity,
    full-text keyword matching, and temporal decay, then re-ranks with
    MMR for result diversity.
    """
    await vector_store_service.get_vector_store(session, vector_store_id)

    query_embedding = (await embed_texts([body.query]))[0]

    if body.search_mode == SearchMode.HYBRID:
        weights = body.ranking_weights
        data = await hybrid_search(
            session=session,
            vector_store_id=vector_store_id,
            query_text=body.query,
            query_embedding=query_embedding,
            max_results=body.max_results,
            filter=body.filter,
            score_threshold=body.score_threshold,
            vector_weight=weights.vector if weights else 0.7,
            text_weight=weights.text if weights else 0.3,
            half_life_days=body.half_life_days,
            mmr_lambda=body.mmr_lambda,
        )
    else:
        data = await search_service.similarity_search(
            session=session,
            vector_store_id=vector_store_id,
            query_embedding=query_embedding,
            max_results=body.max_results,
            filter=body.filter,
            score_threshold=body.score_threshold,
        )

    return SearchResponse(
        data=data,
        search_query=body.query,
        search_mode=body.search_mode,
    )
