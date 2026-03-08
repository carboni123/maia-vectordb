"""Hybrid search combining vector similarity, BM25 text ranking, and temporal decay.

Pipeline:
  Query → Vector Search (4×N) + BM25 Text Search (4×N)
        → Merge by chunk ID → Normalize → Weighted fusion
        → Filter by score_threshold (on pre-decay relevance)
        → MMR Re-rank (Jaccard diversity, on relevance scores)
        → Temporal Decay (half-life multiplier, on final selected set)
        → Return top N
"""

from __future__ import annotations

import logging
import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.schemas.search import ScoreDetails, SearchResult
from maia_vectordb.services.bm25 import bm25_score, parse_tsvector
from maia_vectordb.services.query_filters import build_metadata_clauses

logger = logging.getLogger(__name__)

_CANDIDATE_MULTIPLIER = 4
_WORD_RE = re.compile(r"\w+", re.UNICODE)


# ---------------------------------------------------------------------------
# Internal candidate representation
# ---------------------------------------------------------------------------


@dataclass
class _Candidate:
    """Intermediate result carrying per-signal scores."""

    chunk_id: uuid.UUID
    file_id: uuid.UUID
    filename: str | None
    chunk_index: int
    content: str
    metadata: dict[str, Any] | None
    file_attributes: dict[str, Any] | None
    created_at: datetime
    vector_score: float = 0.0
    text_score: float = 0.0
    temporal_multiplier: float = 1.0
    relevance_score: float = 0.0
    combined_score: float = 0.0
    _token_set: set[str] | None = field(default=None, repr=False, compare=False)

    @property
    def token_set(self) -> set[str]:
        """Lazily tokenize content for Jaccard MMR."""
        if self._token_set is None:
            self._token_set = set(_WORD_RE.findall(self.content.lower()))
        return self._token_set


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def hybrid_search(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
    query_text: str,
    query_embedding: list[float],
    max_results: int,
    metadata_filter: dict[str, Any] | None = None,
    score_threshold: float | None = None,
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    half_life_days: float = 30.0,
    mmr_lambda: float = 0.7,
) -> list[SearchResult]:
    """Run hybrid search and return MMR-reranked results.

    Parameters
    ----------
    session:
        Async database session.
    vector_store_id:
        Scope search to this vector store.
    query_text:
        Raw query string (used for full-text search).
    query_embedding:
        Pre-computed embedding of *query_text* (used for vector similarity).
    max_results:
        Number of final results to return.
    metadata_filter:
        Optional metadata key-value filters.
    score_threshold:
        Minimum relevance score (pre-decay fusion of vector + text).
        Applied before temporal decay so that old-but-relevant documents
        are not accidentally excluded by age.
    vector_weight, text_weight:
        Relative weights for fusion (auto-normalized to sum to 1).
    half_life_days:
        Number of days until a document's score decays to 50%.
        At 2× half-life the score is 25%, etc. Default 30 days.
    mmr_lambda:
        Diversity parameter for MMR (1.0 = pure relevance, 0.0 = pure
        diversity). Default 0.7.
    """
    # Normalize fusion weights
    total = vector_weight + text_weight
    if total > 0:
        vector_weight /= total
        text_weight /= total
    else:
        vector_weight = 1.0
        text_weight = 0.0

    num_candidates = min(max_results * _CANDIDATE_MULTIPLIER, 100)

    # Build filter clauses per alias (avoids fragile string replacement)
    vec_clauses, vec_params = _build_filter_params(
        metadata_filter,
        alias="fc",
    )
    txt_clauses, txt_params = _build_filter_params(
        metadata_filter,
        alias="fc_inner",
    )

    # 1. Retrieve candidates from both retrieval strategies
    vector_candidates = await _vector_candidates(
        session,
        vector_store_id,
        query_embedding,
        num_candidates,
        vec_clauses,
        vec_params,
    )
    text_candidates = await _text_candidates(
        session,
        vector_store_id,
        query_text,
        num_candidates,
        txt_clauses,
        txt_params,
    )

    logger.debug(
        "Candidates retrieved: vector=%d, text=%d",
        len(vector_candidates),
        len(text_candidates),
    )

    # 2. Merge by chunk ID with weighted fusion
    merged = _merge_candidates(vector_candidates, text_candidates)
    if not merged:
        logger.debug("No candidates after merge, returning empty")
        return []

    _min_max_normalize(merged, "vector_score")
    _min_max_normalize(merged, "text_score")

    # Redistribute weight when one signal is entirely absent so that
    # the active signal can reach 1.0 (avoids capping relevance at the
    # weight of the active signal, e.g. max 0.7 when text returns nothing).
    has_vector = any(c.vector_score != 0.0 for c in merged)
    has_text = any(c.text_score != 0.0 for c in merged)
    if not has_text:
        logger.debug("No text signal — redistributing weight to vector")
        vector_weight, text_weight = 1.0, 0.0
    elif not has_vector:
        logger.debug("No vector signal — redistributing weight to text")
        vector_weight, text_weight = 0.0, 1.0

    for c in merged:
        c.relevance_score = vector_weight * c.vector_score + text_weight * c.text_score
        c.combined_score = c.relevance_score

    # 3. Filter by score_threshold on pre-decay relevance
    if score_threshold is not None:
        before = len(merged)
        merged = [c for c in merged if c.relevance_score >= score_threshold]
        logger.debug(
            "Score threshold %.3f: %d → %d candidates",
            score_threshold,
            before,
            len(merged),
        )

    if not merged:
        logger.debug("No candidates after threshold filter, returning empty")
        return []

    # 4. MMR re-ranking for diversity (operates on pure relevance scores
    #    so that age does not distort the diversity/relevance trade-off)
    selected = _mmr_rerank(merged, mmr_lambda, max_results)
    logger.debug("MMR selected %d of %d candidates", len(selected), len(merged))

    # 5. Apply temporal decay as a multiplier (half-life model)
    #    Applied after MMR so diversity decisions are content-driven.
    decay_lambda = math.log(2) / half_life_days
    now = datetime.now(timezone.utc)
    for c in selected:
        age_days = max((now - c.created_at).total_seconds() / 86400.0, 0.0)
        c.temporal_multiplier = math.exp(-decay_lambda * age_days)
        c.combined_score = c.relevance_score * c.temporal_multiplier

    if selected:
        scores = [c.combined_score for c in selected]
        logger.debug(
            "Final %d results: score range [%.4f, %.4f]",
            len(selected),
            min(scores),
            max(scores),
        )

    return [
        SearchResult(
            file_id=str(c.file_id),
            filename=c.filename,
            chunk_index=c.chunk_index,
            content=c.content,
            score=round(c.combined_score, 6),
            metadata=c.metadata,
            file_attributes=c.file_attributes,
            score_details=ScoreDetails(
                vector=round(c.vector_score, 6),
                text=round(c.text_score, 6),
                temporal=round(c.temporal_multiplier, 6),
            ),
        )
        for c in selected
    ]


# ---------------------------------------------------------------------------
# Candidate retrieval
# ---------------------------------------------------------------------------


def _build_filter_params(
    metadata_filter: dict[str, Any] | None,
    *,
    alias: str = "fc",
) -> tuple[list[str], dict[str, Any]]:
    """Build SQL WHERE clauses and params for metadata filters."""
    return build_metadata_clauses(metadata_filter, alias=alias)


async def _vector_candidates(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
    query_embedding: list[float],
    limit: int,
    extra_clauses: list[str],
    extra_params: dict[str, Any],
) -> list[_Candidate]:
    """Top-k candidates ranked by cosine similarity."""
    where = [
        "fc.vector_store_id = :vector_store_id",
        "fc.embedding IS NOT NULL",
        *extra_clauses,
    ]
    params: dict[str, Any] = {
        "vector_store_id": vector_store_id,
        "query_embedding": str(query_embedding),
        "limit": limit,
        **extra_params,
    }
    sql = text(f"""
        SELECT
            fc.id, fc.file_id, fc.chunk_index, fc.content,
            fc.metadata AS chunk_metadata, fc.created_at,
            f.filename, f.attributes AS file_attributes,
            (1 - (fc.embedding <=> :query_embedding)) AS vector_score
        FROM file_chunks fc
        JOIN files f ON f.id = fc.file_id
        WHERE {" AND ".join(where)}
        ORDER BY fc.embedding <=> :query_embedding
        LIMIT :limit
    """)

    result = await session.execute(sql, params)
    return [
        _Candidate(
            chunk_id=row.id,
            file_id=row.file_id,
            filename=row.filename,
            chunk_index=row.chunk_index,
            content=row.content,
            metadata=row.chunk_metadata,
            file_attributes=row.file_attributes,
            created_at=_ensure_tz_aware(row.created_at),
            vector_score=float(row.vector_score),
        )
        for row in result.fetchall()
    ]


async def _text_candidates(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
    query_text: str,
    limit: int,
    extra_clauses: list[str],
    extra_params: dict[str, Any],
) -> list[_Candidate]:
    """Top-k candidates ranked by BM25 (proper TF saturation + IDF + length norm).

    Two-phase approach:
      1. PostgreSQL GIN index handles fast candidate retrieval (``@@``).
      2. Python computes proper BM25 scores for accurate ranking.
    """
    # Phase 1: Get corpus stats and per-term document frequencies
    stats = await _bm25_corpus_stats(session, vector_store_id, query_text)
    if not stats["query_terms"]:
        return []  # query produced no terms after stemming (e.g. all stop words)

    # Phase 2: Fetch matching candidates with tsvector for TF extraction.
    # Uses a CTE so to_tsvector is computed once in SELECT and reused in
    # the outer ORDER BY (the GIN index handles the WHERE @@ filter).
    # extra_clauses already use the fc_inner alias (built by caller).
    cte_extra = ""
    if extra_clauses:
        cte_extra = " AND " + " AND ".join(extra_clauses)

    params: dict[str, Any] = {
        "vector_store_id": vector_store_id,
        "query_text": query_text,
        "limit": limit,
        **extra_params,
    }
    sql = text(f"""
        WITH fc AS (
            SELECT
                fc_inner.*,
                to_tsvector('english', fc_inner.content) AS tsv
            FROM file_chunks fc_inner
            WHERE fc_inner.vector_store_id = :vector_store_id
              AND to_tsvector('english', fc_inner.content)
                  @@ plainto_tsquery('english', :query_text)
              {cte_extra}
        )
        SELECT
            fc.id, fc.file_id, fc.chunk_index, fc.content,
            fc.metadata AS chunk_metadata, fc.created_at,
            fc.token_count,
            fc.tsv::text AS doc_tsvector,
            f.filename, f.attributes AS file_attributes
        FROM fc
        JOIN files f ON f.id = fc.file_id
        ORDER BY ts_rank_cd(
            fc.tsv,
            plainto_tsquery('english', :query_text)
        ) DESC
        LIMIT :limit
    """)

    result = await session.execute(sql, params)
    candidates: list[_Candidate] = []

    for row in result.fetchall():
        # Parse tsvector and compute BM25 score
        doc_tfs = parse_tsvector(row.doc_tsvector) if row.doc_tsvector else {}
        score = bm25_score(
            query_terms=stats["query_terms"],
            doc_tfs=doc_tfs,
            doc_length=row.token_count or 1,
            total_docs=stats["total_docs"],
            avg_dl=stats["avg_dl"],
            doc_freqs=stats["doc_freqs"],
        )
        candidates.append(
            _Candidate(
                chunk_id=row.id,
                file_id=row.file_id,
                filename=row.filename,
                chunk_index=row.chunk_index,
                content=row.content,
                metadata=row.chunk_metadata,
                file_attributes=row.file_attributes,
                created_at=_ensure_tz_aware(row.created_at),
                text_score=score,
            )
        )

    # Re-sort by BM25 score (may differ from the DB's ts_rank_cd order)
    candidates.sort(key=lambda c: c.text_score, reverse=True)
    return candidates


async def _bm25_corpus_stats(
    session: AsyncSession,
    vector_store_id: uuid.UUID,
    query_text: str,
) -> dict[str, Any]:
    """Fetch corpus-level statistics needed for BM25 scoring.

    Returns dict with keys: total_docs, avg_dl, query_terms, doc_freqs.
    """
    sql = text("""
        WITH corpus_stats AS (
            SELECT
                COUNT(*)::int AS total_docs,
                COALESCE(AVG(token_count), 1)::float AS avg_dl
            FROM file_chunks
            WHERE vector_store_id = :vector_store_id
        ),
        query_terms AS (
            SELECT lexeme::text AS term
            FROM unnest(to_tsvector('english', :query_text))
                AS t(lexeme, positions, weights)
        ),
        doc_freqs AS (
            SELECT
                qt.term,
                COUNT(fc.id)::int AS df
            FROM query_terms qt
            LEFT JOIN file_chunks fc
                ON fc.vector_store_id = :vector_store_id
                AND to_tsvector('english', fc.content)
                    @@ to_tsquery('simple', qt.term)
            GROUP BY qt.term
        )
        SELECT cs.total_docs, cs.avg_dl, df.term, df.df
        FROM corpus_stats cs
        CROSS JOIN doc_freqs df
    """)

    result = await session.execute(
        sql,
        {"vector_store_id": vector_store_id, "query_text": query_text},
    )
    rows = result.fetchall()

    if not rows:
        return {"total_docs": 0, "avg_dl": 1.0, "query_terms": [], "doc_freqs": {}}

    return {
        "total_docs": rows[0].total_docs,
        "avg_dl": float(rows[0].avg_dl),
        "query_terms": [r.term for r in rows],
        "doc_freqs": {r.term: r.df for r in rows},
    }


# ---------------------------------------------------------------------------
# Score merging & normalization
# ---------------------------------------------------------------------------


def _merge_candidates(
    vector_list: list[_Candidate],
    text_list: list[_Candidate],
) -> list[_Candidate]:
    """Merge two candidate lists by chunk_id, keeping the best scores."""
    by_id: dict[uuid.UUID, _Candidate] = {}

    for c in vector_list:
        by_id[c.chunk_id] = c

    for c in text_list:
        if c.chunk_id in by_id:
            by_id[c.chunk_id].text_score = c.text_score
        else:
            by_id[c.chunk_id] = c

    return list(by_id.values())


def _min_max_normalize(candidates: list[_Candidate], attr: str) -> None:
    """Normalize a score attribute to [0, 1] across candidates (in-place)."""
    if not candidates:
        return
    values = [getattr(c, attr) for c in candidates]
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:
        # All equal — set to 1.0 if nonzero, 0.0 otherwise
        norm = 1.0 if hi > 0 else 0.0
        for c in candidates:
            setattr(c, attr, norm)
    else:
        for c in candidates:
            setattr(c, attr, (getattr(c, attr) - lo) / span)


# ---------------------------------------------------------------------------
# MMR re-ranking (Jaccard-based)
# ---------------------------------------------------------------------------


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def _mmr_rerank(
    candidates: list[_Candidate],
    mmr_lambda: float,
    k: int,
) -> list[_Candidate]:
    """Greedily select *k* results using Maximal Marginal Relevance.

    MMR(d) = λ * relevance_score(d)
             - (1 - λ) * max(jaccard_sim(d, d_j) for d_j in selected)

    Uses Jaccard similarity on token sets (cheap, works without embeddings).
    Operates on pre-decay ``relevance_score`` so that age does not distort
    the diversity/relevance trade-off.
    """
    if not candidates:
        return []

    remaining = sorted(candidates, key=lambda c: c.relevance_score, reverse=True)

    # Fast path: pure relevance ranking (no diversity penalty)
    if mmr_lambda >= 1.0:
        return remaining[:k]

    selected: list[_Candidate] = [remaining.pop(0)]

    while len(selected) < k and remaining:
        best_mmr = -float("inf")
        best_idx = 0

        for i, cand in enumerate(remaining):
            relevance = cand.relevance_score

            # Diversity penalty: max Jaccard similarity to any selected doc
            max_sim = max(
                (_jaccard_similarity(cand.token_set, s.token_set) for s in selected),
                default=0.0,
            )

            mmr = mmr_lambda * relevance - (1 - mmr_lambda) * max_sim

            if mmr > best_mmr:
                best_mmr = mmr
                best_idx = i

        selected.append(remaining.pop(best_idx))

    return selected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_tz_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (default to UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
