"""Tests for the hybrid search service.

Pipeline under test:
  Vector (4×N) + Text (4×N) → Merge → Normalize → Fuse
  → Threshold (pre-decay) → MMR (on relevance) → Temporal Decay → Top N
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from maia_vectordb.schemas.search import RankingWeights
from maia_vectordb.services.hybrid_search import (
    _Candidate,
    _jaccard_similarity,
    _merge_candidates,
    _min_max_normalize,
    _mmr_rerank,
    hybrid_search,
)
from tests.conftest import make_store

_EMBEDDING_DIM = 1536
# Use a live "now" so tests don't rot. Individual tests that need exact
# temporal multiplier values patch datetime.now instead.
_NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _candidate(
    *,
    chunk_id: uuid.UUID | None = None,
    content: str = "test",
    vector_score: float = 0.0,
    text_score: float = 0.0,
    created_at: datetime | None = None,
) -> _Candidate:
    return _Candidate(
        chunk_id=chunk_id or uuid.uuid4(),
        file_id=uuid.uuid4(),
        filename="doc.txt",
        chunk_index=0,
        content=content,
        metadata=None,
        file_attributes=None,
        created_at=created_at or _NOW,
        vector_score=vector_score,
        text_score=text_score,
    )


# ---------------------------------------------------------------------------
# _jaccard_similarity
# ---------------------------------------------------------------------------


class TestJaccardSimilarity:
    def test_identical_sets(self) -> None:
        s = {"hello", "world"}
        assert _jaccard_similarity(s, s) == pytest.approx(1.0)

    def test_disjoint_sets(self) -> None:
        assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == pytest.approx(0.0)

    def test_partial_overlap(self) -> None:
        # intersection=1, union=3
        assert _jaccard_similarity({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)

    def test_empty_sets(self) -> None:
        assert _jaccard_similarity(set(), {"a"}) == 0.0
        assert _jaccard_similarity(set(), set()) == 0.0


# ---------------------------------------------------------------------------
# _merge_candidates
# ---------------------------------------------------------------------------


class TestMergeCandidates:
    def test_disjoint_sets(self) -> None:
        v = [_candidate(content="a", vector_score=0.9)]
        b = [_candidate(content="b", text_score=0.8)]
        merged = _merge_candidates(v, b)
        assert len(merged) == 2

    def test_overlapping_candidates(self) -> None:
        shared_id = uuid.uuid4()
        v = [_candidate(chunk_id=shared_id, vector_score=0.9)]
        b = [_candidate(chunk_id=shared_id, text_score=0.8)]
        merged = _merge_candidates(v, b)
        assert len(merged) == 1
        assert merged[0].vector_score == 0.9
        assert merged[0].text_score == 0.8

    def test_empty_inputs(self) -> None:
        assert _merge_candidates([], []) == []


# ---------------------------------------------------------------------------
# _min_max_normalize
# ---------------------------------------------------------------------------


class TestMinMaxNormalize:
    def test_normalizes_range(self) -> None:
        cs = [
            _candidate(vector_score=0.2),
            _candidate(vector_score=0.6),
            _candidate(vector_score=1.0),
        ]
        _min_max_normalize(cs, "vector_score")
        assert cs[0].vector_score == pytest.approx(0.0)
        assert cs[1].vector_score == pytest.approx(0.5)
        assert cs[2].vector_score == pytest.approx(1.0)

    def test_all_equal_nonzero(self) -> None:
        cs = [_candidate(vector_score=0.5), _candidate(vector_score=0.5)]
        _min_max_normalize(cs, "vector_score")
        assert all(c.vector_score == 1.0 for c in cs)

    def test_all_zero(self) -> None:
        cs = [_candidate(vector_score=0.0), _candidate(vector_score=0.0)]
        _min_max_normalize(cs, "vector_score")
        assert all(c.vector_score == 0.0 for c in cs)

    def test_empty_list(self) -> None:
        _min_max_normalize([], "vector_score")  # no error


# ---------------------------------------------------------------------------
# Temporal decay (half-life model)
# ---------------------------------------------------------------------------


class TestTemporalDecay:
    def test_half_life_at_30_days(self) -> None:
        """At exactly half_life_days, the multiplier should be 0.5."""
        decay_lambda = math.log(2) / 30.0
        age_days = 30.0
        multiplier = math.exp(-decay_lambda * age_days)
        assert multiplier == pytest.approx(0.5)

    def test_double_half_life(self) -> None:
        """At 2× half-life, the multiplier should be 0.25."""
        decay_lambda = math.log(2) / 30.0
        age_days = 60.0
        multiplier = math.exp(-decay_lambda * age_days)
        assert multiplier == pytest.approx(0.25)

    def test_zero_age(self) -> None:
        """Brand new documents have multiplier 1.0."""
        decay_lambda = math.log(2) / 30.0
        multiplier = math.exp(-decay_lambda * 0.0)
        assert multiplier == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _mmr_rerank (Jaccard-based)
# ---------------------------------------------------------------------------


class TestMMRRerank:
    def test_returns_k_results(self) -> None:
        cs = [_candidate(content=f"doc {i} unique{i}") for i in range(10)]
        for i, c in enumerate(cs):
            c.relevance_score = 1.0 - i * 0.1
        result = _mmr_rerank(cs, mmr_lambda=0.7, k=5)
        assert len(result) == 5

    def test_respects_relevance_with_lambda_1(self) -> None:
        """With lambda=1 (pure relevance), order is by relevance_score."""
        cs = [_candidate(content="low"), _candidate(content="high")]
        cs[0].relevance_score = 0.3
        cs[1].relevance_score = 0.9
        result = _mmr_rerank(cs, mmr_lambda=1.0, k=2)
        assert result[0].content == "high"
        assert result[1].content == "low"

    def test_diversity_with_low_lambda(self) -> None:
        """With low lambda, near-duplicate docs are penalized."""
        cs = [
            _candidate(content="the quick brown fox jumps"),
            _candidate(content="the quick brown fox leaps"),  # near-duplicate
            _candidate(content="database schema migration guide"),  # diverse
        ]
        cs[0].relevance_score = 1.0
        cs[1].relevance_score = 0.95
        cs[2].relevance_score = 0.5

        result = _mmr_rerank(cs, mmr_lambda=0.3, k=3)
        assert result[0].content == "the quick brown fox jumps"
        # Diverse doc should be picked before the near-duplicate
        assert result[1].content == "database schema migration guide"

    def test_fewer_candidates_than_k(self) -> None:
        cs = [_candidate(content="only")]
        cs[0].relevance_score = 0.9
        result = _mmr_rerank(cs, mmr_lambda=0.7, k=5)
        assert len(result) == 1

    def test_empty_candidates(self) -> None:
        assert _mmr_rerank([], mmr_lambda=0.7, k=5) == []


# ---------------------------------------------------------------------------
# RankingWeights validation (M-5)
# ---------------------------------------------------------------------------


class TestRankingWeightsValidation:
    def test_rejects_all_zero_weights(self) -> None:
        """Both weights at 0 should raise a validation error."""
        with pytest.raises(ValueError, match="At least one ranking weight"):
            RankingWeights(vector=0.0, text=0.0)

    def test_accepts_one_zero(self) -> None:
        """One weight at 0 is fine (pure vector or pure text)."""
        w = RankingWeights(vector=1.0, text=0.0)
        assert w.vector == 1.0

    def test_defaults_are_valid(self) -> None:
        w = RankingWeights()
        assert w.vector == 0.7
        assert w.text == 0.3


# ---------------------------------------------------------------------------
# hybrid_search (integration with mocked DB)
# ---------------------------------------------------------------------------


def _make_vector_row(
    *,
    chunk_id: uuid.UUID | None = None,
    file_id: uuid.UUID | None = None,
    content: str = "vector match",
    vector_score: float = 0.9,
    created_at: datetime | None = None,
) -> Any:
    row = MagicMock()
    row.id = chunk_id or uuid.uuid4()
    row.file_id = file_id or uuid.uuid4()
    row.chunk_index = 0
    row.content = content
    row.chunk_metadata = None
    row.created_at = created_at or _NOW
    row.filename = "doc.txt"
    row.file_attributes = None
    row.vector_score = vector_score
    return row


def _make_text_row(
    *,
    chunk_id: uuid.UUID | None = None,
    file_id: uuid.UUID | None = None,
    content: str = "keyword match",
    doc_tsvector: str = "'keyword':1 'match':2",
    token_count: int = 50,
    created_at: datetime | None = None,
) -> Any:
    row = MagicMock()
    row.id = chunk_id or uuid.uuid4()
    row.file_id = file_id or uuid.uuid4()
    row.chunk_index = 0
    row.content = content
    row.chunk_metadata = None
    row.created_at = created_at or _NOW
    row.token_count = token_count
    row.doc_tsvector = doc_tsvector
    row.filename = "doc.txt"
    row.file_attributes = None
    return row


def _make_stats_row(
    *, term: str, df: int = 5, total_docs: int = 100, avg_dl: float = 50.0,
) -> Any:
    row = MagicMock()
    row.total_docs = total_docs
    row.avg_dl = avg_dl
    row.term = term
    row.df = df
    return row


def _make_stats_result(*terms: str) -> MagicMock:
    """Create a mock result for the BM25 corpus stats query."""
    result = MagicMock()
    result.fetchall.return_value = [
        _make_stats_row(term=t) for t in terms
    ]
    return result


class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_returns_merged_results(self) -> None:
        """Hybrid search merges vector and text candidates."""
        session = MagicMock()

        vector_result = MagicMock()
        vector_result.fetchall.return_value = [
            _make_vector_row(content="vec1", vector_score=0.9),
            _make_vector_row(content="vec2", vector_score=0.7),
        ]
        stats_result = _make_stats_result("test", "queri")
        text_result = MagicMock()
        text_result.fetchall.return_value = [
            _make_text_row(content="text1", doc_tsvector="'test':1 'queri':2"),
        ]
        session.execute = AsyncMock(
            side_effect=[vector_result, stats_result, text_result],
        )

        results = await hybrid_search(
            session=session,
            vector_store_id=uuid.uuid4(),
            query_text="test query",
            query_embedding=[0.1] * _EMBEDDING_DIM,
            max_results=10,
        )

        assert len(results) == 3
        for r in results:
            assert r.score_details is not None

    @pytest.mark.asyncio
    async def test_vector_only_relevance_reaches_one(self) -> None:
        """When text search returns nothing, the best vector match should
        get relevance 1.0 (weights redistribute to the active signal)."""
        session = MagicMock()

        vector_result = MagicMock()
        vector_result.fetchall.return_value = [
            _make_vector_row(content="perfect", vector_score=0.95),
        ]
        empty_stats = MagicMock()
        empty_stats.fetchall.return_value = []
        session.execute = AsyncMock(side_effect=[vector_result, empty_stats])

        results = await hybrid_search(
            session=session,
            vector_store_id=uuid.uuid4(),
            query_text="the",  # likely all stop words
            query_embedding=[0.1] * _EMBEDDING_DIM,
            max_results=10,
            score_threshold=0.9,
        )

        # Without adaptive weights this would be capped at 0.7 and filtered out
        assert len(results) == 1
        assert results[0].score_details is not None
        assert results[0].score_details.vector == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_text_only_relevance_reaches_one(self) -> None:
        """When vector search returns nothing, the best text match should
        get relevance 1.0 (weights redistribute to the active signal)."""
        session = MagicMock()

        vector_result = MagicMock()
        vector_result.fetchall.return_value = []
        stats_result = _make_stats_result("test")
        text_result = MagicMock()
        text_result.fetchall.return_value = [
            _make_text_row(content="test match", doc_tsvector="'test':1"),
        ]
        session.execute = AsyncMock(
            side_effect=[vector_result, stats_result, text_result],
        )

        results = await hybrid_search(
            session=session,
            vector_store_id=uuid.uuid4(),
            query_text="test",
            query_embedding=[0.1] * _EMBEDDING_DIM,
            max_results=10,
            score_threshold=0.9,
        )

        # Without adaptive weights this would be capped at 0.3 and filtered out
        assert len(results) == 1
        assert results[0].score_details is not None
        assert results[0].score_details.text == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_score_threshold_filters_on_pre_decay_relevance(self) -> None:
        """score_threshold applies to pre-decay relevance, not post-decay score.

        This ensures old-but-relevant documents are not accidentally excluded
        by temporal decay. (Fix for M-1)
        """
        session = MagicMock()

        old_date = _NOW - timedelta(days=100)  # temporal multiplier ≈ 0.1

        vector_result = MagicMock()
        vector_result.fetchall.return_value = [
            # High relevance but very old → post-decay score will be low
            _make_vector_row(content="old but relevant", vector_score=0.9,
                             created_at=old_date),
            # Low relevance
            _make_vector_row(content="irrelevant", vector_score=0.1),
        ]
        # Text search: empty stats → no terms → no text candidates
        empty_stats = MagicMock()
        empty_stats.fetchall.return_value = []
        session.execute = AsyncMock(side_effect=[vector_result, empty_stats])

        results = await hybrid_search(
            session=session,
            vector_store_id=uuid.uuid4(),
            query_text="test",
            query_embedding=[0.1] * _EMBEDDING_DIM,
            max_results=10,
            score_threshold=0.5,
            half_life_days=30.0,
        )

        # The old-but-relevant doc should survive (relevance=1.0 >= 0.5)
        # even though its post-decay score is much lower
        assert len(results) == 1
        assert results[0].content == "old but relevant"
        # The post-decay score should be well below the threshold
        assert results[0].score < 0.5

    @pytest.mark.asyncio
    async def test_temporal_decay_favors_recent(self) -> None:
        """Recent documents get higher scores via temporal multiplier."""
        session = MagicMock()

        old_date = _NOW - timedelta(days=100)
        recent_date = _NOW - timedelta(days=1)

        vector_result = MagicMock()
        vector_result.fetchall.return_value = [
            _make_vector_row(content="old", vector_score=0.8, created_at=old_date),
            _make_vector_row(
                content="recent", vector_score=0.8,
                created_at=recent_date,
            ),
        ]
        empty_stats = MagicMock()
        empty_stats.fetchall.return_value = []
        session.execute = AsyncMock(side_effect=[vector_result, empty_stats])

        results = await hybrid_search(
            session=session,
            vector_store_id=uuid.uuid4(),
            query_text="test",
            query_embedding=[0.1] * _EMBEDDING_DIM,
            max_results=10,
            half_life_days=30.0,
        )

        by_content = {r.content: r for r in results}
        assert by_content["recent"].score_details is not None
        assert by_content["old"].score_details is not None
        assert (
            by_content["recent"].score_details.temporal
            > by_content["old"].score_details.temporal
        )
        assert by_content["recent"].score > by_content["old"].score

    @pytest.mark.asyncio
    @patch("maia_vectordb.services.hybrid_search.datetime")
    async def test_half_life_multiplier_correct(
        self, mock_dt: MagicMock,
    ) -> None:
        """At exactly half_life_days, score should be ~50% of a fresh doc."""
        fixed_now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        session = MagicMock()
        half_life = 30.0

        vector_result = MagicMock()
        vector_result.fetchall.return_value = [
            _make_vector_row(
                content="aged", vector_score=0.9,
                created_at=fixed_now - timedelta(days=30),
            ),
        ]
        empty_stats = MagicMock()
        empty_stats.fetchall.return_value = []
        session.execute = AsyncMock(side_effect=[vector_result, empty_stats])

        results = await hybrid_search(
            session=session,
            vector_store_id=uuid.uuid4(),
            query_text="test",
            query_embedding=[0.1] * _EMBEDDING_DIM,
            max_results=10,
            half_life_days=half_life,
        )

        assert len(results) == 1
        assert results[0].score_details is not None
        assert results[0].score_details.temporal == pytest.approx(0.5, abs=0.001)

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        """Returns empty list when no candidates found."""
        session = MagicMock()

        empty_result = MagicMock()
        empty_result.fetchall.return_value = []
        session.execute = AsyncMock(return_value=empty_result)

        results = await hybrid_search(
            session=session,
            vector_store_id=uuid.uuid4(),
            query_text="nothing",
            query_embedding=[0.1] * _EMBEDDING_DIM,
            max_results=10,
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_overlapping_candidates_merged(self) -> None:
        """A chunk appearing in both retrieval sets is merged correctly."""
        session = MagicMock()
        shared_id = uuid.uuid4()
        shared_file_id = uuid.uuid4()

        vector_result = MagicMock()
        vector_result.fetchall.return_value = [
            _make_vector_row(
                chunk_id=shared_id, file_id=shared_file_id,
                content="shared", vector_score=0.9,
            ),
        ]
        stats_result = _make_stats_result("share")
        text_result = MagicMock()
        text_result.fetchall.return_value = [
            _make_text_row(
                chunk_id=shared_id, file_id=shared_file_id,
                content="shared", doc_tsvector="'share':1",
            ),
        ]
        session.execute = AsyncMock(
            side_effect=[vector_result, stats_result, text_result],
        )

        results = await hybrid_search(
            session=session,
            vector_store_id=uuid.uuid4(),
            query_text="shared",
            query_embedding=[0.1] * _EMBEDDING_DIM,
            max_results=10,
        )

        assert len(results) == 1
        assert results[0].score_details is not None
        assert results[0].score_details.vector > 0
        assert results[0].score_details.text > 0

    @pytest.mark.asyncio
    async def test_candidate_multiplier_is_4x(self) -> None:
        """Vector search should request 4× max_results candidates."""
        session = MagicMock()

        empty_result = MagicMock()
        empty_result.fetchall.return_value = []
        session.execute = AsyncMock(return_value=empty_result)

        await hybrid_search(
            session=session,
            vector_store_id=uuid.uuid4(),
            query_text="test",
            query_embedding=[0.1] * _EMBEDDING_DIM,
            max_results=5,
        )

        # First call is vector search — should use limit=20 (5 * 4)
        first_call = session.execute.call_args_list[0]
        assert first_call[0][1]["limit"] == 20


# ---------------------------------------------------------------------------
# API endpoint with search_mode=hybrid
# ---------------------------------------------------------------------------


class TestHybridSearchEndpoint:
    @patch("maia_vectordb.api.search.hybrid_search")
    @patch("maia_vectordb.api.search.embed_texts")
    def test_hybrid_mode_calls_hybrid_search(
        self,
        mock_embed: MagicMock,
        mock_hybrid: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """search_mode=hybrid routes to the hybrid search service."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)
        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]
        mock_hybrid.return_value = []

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "test", "search_mode": "hybrid"},
        )

        assert resp.status_code == 200
        assert resp.json()["search_mode"] == "hybrid"
        mock_hybrid.assert_called_once()

    @patch("maia_vectordb.api.search.embed_texts")
    def test_vector_mode_uses_standard_search(
        self,
        mock_embed: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """search_mode=vector (default) uses standard similarity search."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)
        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]

        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "test"},
        )

        assert resp.status_code == 200
        assert resp.json()["search_mode"] == "vector"

    @patch("maia_vectordb.api.search.hybrid_search")
    @patch("maia_vectordb.api.search.embed_texts")
    def test_custom_ranking_weights(
        self,
        mock_embed: MagicMock,
        mock_hybrid: MagicMock,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """Custom ranking_weights and half_life_days are forwarded."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        mock_session.get = AsyncMock(return_value=store)
        mock_embed.return_value = [[0.1] * _EMBEDDING_DIM]
        mock_hybrid.return_value = []

        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "test",
                "search_mode": "hybrid",
                "ranking_weights": {"vector": 0.6, "text": 0.4},
                "half_life_days": 14,
                "mmr_lambda": 0.6,
            },
        )

        assert resp.status_code == 200
        call_kwargs = mock_hybrid.call_args.kwargs
        assert call_kwargs["vector_weight"] == 0.6
        assert call_kwargs["text_weight"] == 0.4
        assert call_kwargs["half_life_days"] == 14
        assert call_kwargs["mmr_lambda"] == 0.6

    def test_zero_ranking_weights_returns_422(
        self, client: TestClient, mock_session: MagicMock,
    ) -> None:
        """Both weights at 0 should return a validation error."""
        store_id = uuid.uuid4()
        resp = client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "test",
                "search_mode": "hybrid",
                "ranking_weights": {"vector": 0.0, "text": 0.0},
            },
        )
        assert resp.status_code == 422
