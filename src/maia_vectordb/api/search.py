"""Similarity search endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from maia_vectordb.api.deps import DBSession
from maia_vectordb.schemas.search import SearchRequest, SearchResponse
from maia_vectordb.services import search_service, vector_store_service
from maia_vectordb.services.embedding import embed_texts

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
    """Perform cosine similarity search over a vector store.

    Embeds the query string on-the-fly, searches using pgvector ``<=>``
    operator, applies optional metadata filters and score threshold, and
    returns top-k results ranked by similarity.
    """
    await vector_store_service.get_vector_store(session, vector_store_id)

    query_embedding = (await embed_texts([body.query]))[0]

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
    )
