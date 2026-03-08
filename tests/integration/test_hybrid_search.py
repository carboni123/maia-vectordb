"""Integration tests for hybrid search against real PostgreSQL + pgvector.

Exercises the full hybrid search pipeline — vector retrieval, BM25 text
scoring, adaptive weight normalization, score threshold, MMR diversity,
and temporal decay — all against a live database with mock embeddings.

Run with:
    uv run pytest tests/integration/test_hybrid_search.py -v -m integration
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Documents with distinct topics so BM25 (keyword) and vector (semantic) give
# meaningfully different rankings even with mock embeddings.
_DOCS = {
    "python_intro": (
        "Python is a high-level programming language known for its clean syntax "
        "and readability. It supports multiple paradigms including object-oriented, "
        "functional, and procedural programming. Python is widely used in web "
        "development, data science, machine learning, and automation."
    ),
    "rust_intro": (
        "Rust is a systems programming language focused on safety, speed, and "
        "concurrency. It prevents memory bugs at compile time through its ownership "
        "model. Rust is used for operating systems, game engines, and embedded "
        "systems where performance and reliability are critical."
    ),
    "database_guide": (
        "PostgreSQL is a powerful open-source relational database system. It "
        "supports advanced features like full-text search, JSON storage, and "
        "the pgvector extension for vector similarity search. PostgreSQL is "
        "widely used for web applications and analytical workloads."
    ),
    "cooking_recipe": (
        "To make a classic Italian pasta, boil salted water and cook spaghetti "
        "for eight minutes until al dente. Meanwhile, sauté garlic in olive oil, "
        "add crushed tomatoes, basil, and a pinch of red pepper flakes. Toss the "
        "drained pasta with the sauce and serve with parmesan cheese."
    ),
    "machine_learning": (
        "Machine learning algorithms learn patterns from data without being "
        "explicitly programmed. Supervised learning uses labeled training data, "
        "while unsupervised learning finds hidden structure. Deep learning uses "
        "neural networks with many layers to model complex relationships in "
        "images, text, and speech."
    ),
}


async def _create_store_with_docs(
    client: AsyncClient,
    store_name: str,
    docs: dict[str, str] | None = None,
) -> tuple[str, dict[str, str]]:
    """Create a vector store and upload documents.

    Returns (store_id, {name: file_id}).
    """
    if docs is None:
        docs = _DOCS

    resp = await client.post("/v1/vector_stores", json={"name": store_name})
    assert resp.status_code == 201
    store_id = resp.json()["id"]

    file_ids: dict[str, str] = {}
    for name, content in docs.items():
        resp = await client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={"file": (f"{name}.txt", content.encode(), "text/plain")},
        )
        assert resp.status_code == 201, resp.text
        file_ids[name] = resp.json()["id"]

    return store_id, file_ids


# ============================================================================
# A. Hybrid Search Basics
# ============================================================================


class TestHybridSearchBasics:
    """Verify hybrid search returns results with correct structure."""

    async def test_hybrid_search_returns_results(
        self, integration_client: AsyncClient,
    ) -> None:
        """Hybrid search returns results with score_details breakdown."""
        store_id, _ = await _create_store_with_docs(
            integration_client, "hybrid-basics",
        )

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "programming language",
                "search_mode": "hybrid",
                "max_results": 5,
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["search_mode"] == "hybrid"
        assert len(body["data"]) >= 1

        # Every hybrid result has score_details with vector, text, temporal
        for result in body["data"]:
            assert result["score_details"] is not None
            sd = result["score_details"]
            assert "vector" in sd
            assert "text" in sd
            assert "temporal" in sd
            assert 0.0 <= sd["vector"] <= 1.0
            assert 0.0 <= sd["text"] <= 1.0
            assert 0.0 < sd["temporal"] <= 1.0

    async def test_hybrid_vs_vector_mode_structure(
        self, integration_client: AsyncClient,
    ) -> None:
        """Vector mode returns null score_details; hybrid mode returns breakdown."""
        store_id, _ = await _create_store_with_docs(
            integration_client, "hybrid-vs-vector",
            docs={"doc": _DOCS["python_intro"]},
        )

        vector_resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "Python programming", "search_mode": "vector"},
        )
        hybrid_resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "Python programming", "search_mode": "hybrid"},
        )

        assert vector_resp.status_code == 200
        assert hybrid_resp.status_code == 200

        for r in vector_resp.json()["data"]:
            assert r["score_details"] is None

        for r in hybrid_resp.json()["data"]:
            assert r["score_details"] is not None

    async def test_hybrid_search_empty_store(
        self, integration_client: AsyncClient,
    ) -> None:
        """Hybrid search on an empty store returns an empty list."""
        resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "hybrid-empty"},
        )
        store_id = resp.json()["id"]

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "anything", "search_mode": "hybrid"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ============================================================================
# B. BM25 Keyword Matching
# ============================================================================


class TestBM25KeywordMatching:
    """Verify that BM25 text scoring contributes to hybrid results."""

    async def test_keyword_match_boosts_results(
        self, integration_client: AsyncClient,
    ) -> None:
        """Documents containing exact query keywords get a text score boost."""
        store_id, _ = await _create_store_with_docs(
            integration_client, "bm25-keyword",
        )

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "spaghetti garlic tomatoes pasta",
                "search_mode": "hybrid",
                "max_results": 5,
            },
        )

        assert resp.status_code == 200
        results = resp.json()["data"]
        assert len(results) >= 1

        # The cooking recipe should appear and have a non-zero text score
        # since it contains exact keyword matches
        cooking_results = [
            r for r in results
            if "spaghetti" in r["content"].lower() or "pasta" in r["content"].lower()
        ]
        assert len(cooking_results) >= 1, "Expected cooking recipe in results"
        assert cooking_results[0]["score_details"]["text"] > 0

    async def test_text_weight_one_favors_keywords(
        self, integration_client: AsyncClient,
    ) -> None:
        """With text_weight=1.0, results are ranked purely by BM25 keywords."""
        store_id, _ = await _create_store_with_docs(
            integration_client, "bm25-pure-text",
        )

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "PostgreSQL pgvector vector similarity",
                "search_mode": "hybrid",
                "ranking_weights": {"vector": 0.0, "text": 1.0},
                "max_results": 3,
            },
        )

        assert resp.status_code == 200
        results = resp.json()["data"]
        assert len(results) >= 1

        # Top result should be the database guide (contains all keywords)
        top = results[0]
        assert "postgresql" in top["content"].lower()


# ============================================================================
# C. Score Threshold
# ============================================================================


class TestScoreThreshold:
    """Verify score_threshold filtering works correctly in hybrid mode."""

    async def test_high_threshold_filters_results(
        self, integration_client: AsyncClient,
    ) -> None:
        """A very high threshold filters out most or all results."""
        store_id, _ = await _create_store_with_docs(
            integration_client, "threshold-high",
        )

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "quantum entanglement dark matter",
                "search_mode": "hybrid",
                "score_threshold": 0.99,
                "max_results": 10,
            },
        )

        assert resp.status_code == 200
        # With an unrelated query and very high threshold, expect few or no results
        assert len(resp.json()["data"]) <= 1

    async def test_low_threshold_returns_more(
        self, integration_client: AsyncClient,
    ) -> None:
        """Lower threshold returns more results than a high threshold."""
        store_id, _ = await _create_store_with_docs(
            integration_client, "threshold-compare",
        )

        query = "programming and data"
        low = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": query,
                "search_mode": "hybrid",
                "score_threshold": 0.01,
                "max_results": 10,
            },
        )
        high = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": query,
                "search_mode": "hybrid",
                "score_threshold": 0.9,
                "max_results": 10,
            },
        )

        assert low.status_code == 200
        assert high.status_code == 200
        assert len(low.json()["data"]) >= len(high.json()["data"])


# ============================================================================
# D. Temporal Decay
# ============================================================================


class TestTemporalDecay:
    """Verify temporal decay multiplier affects hybrid search scores."""

    async def test_recent_docs_score_higher(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Documents with recent created_at get higher scores than old ones."""
        store_id, file_ids = await _create_store_with_docs(
            integration_client, "decay-recent",
            docs={
                "old_doc": "Python is used for web development and scripting.",
                "new_doc": "Python is used for web development and automation.",
            },
        )

        # Backdate one document's chunks to 90 days ago
        old_file_id = file_ids["old_doc"]
        old_date = datetime.now(timezone.utc) - timedelta(days=90)
        await db_session.execute(
            text(
                "UPDATE file_chunks SET created_at = :old_date "
                "WHERE file_id = :file_id"
            ),
            {"old_date": old_date, "file_id": old_file_id},
        )
        await db_session.commit()

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "Python web development",
                "search_mode": "hybrid",
                "half_life_days": 30.0,
                "max_results": 5,
            },
        )

        assert resp.status_code == 200
        results = resp.json()["data"]
        assert len(results) >= 2

        # Find results by file_id
        old_results = [r for r in results if r["file_id"] == old_file_id]
        new_results = [r for r in results if r["file_id"] == file_ids["new_doc"]]

        assert len(old_results) >= 1
        assert len(new_results) >= 1

        # The old doc should have a lower temporal multiplier
        # ~90 days with 30-day half-life → temporal ≈ 0.125
        assert old_results[0]["score_details"]["temporal"] < 0.25
        assert new_results[0]["score_details"]["temporal"] > 0.95  # nearly fresh

    async def test_short_half_life_penalizes_more(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """A shorter half-life produces stronger decay for the same age."""
        store_id, file_ids = await _create_store_with_docs(
            integration_client, "decay-halflife",
            docs={"aged_doc": "Neural networks process information in layers."},
        )

        # Set the document to 15 days old
        aged_date = datetime.now(timezone.utc) - timedelta(days=15)
        await db_session.execute(
            text(
                "UPDATE file_chunks SET created_at = :d WHERE file_id = :fid"
            ),
            {"d": aged_date, "fid": file_ids["aged_doc"]},
        )
        await db_session.commit()

        # Search with long half-life (30 days)
        long_resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "neural networks",
                "search_mode": "hybrid",
                "half_life_days": 30.0,
                "max_results": 5,
            },
        )
        # Search with short half-life (7 days)
        short_resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "neural networks",
                "search_mode": "hybrid",
                "half_life_days": 7.0,
                "max_results": 5,
            },
        )

        assert long_resp.status_code == 200
        assert short_resp.status_code == 200

        long_score = long_resp.json()["data"][0]["score"]
        short_score = short_resp.json()["data"][0]["score"]

        # Shorter half-life → more decay → lower score
        assert short_score < long_score


# ============================================================================
# E. MMR Diversity
# ============================================================================


class TestMMRDiversity:
    """Verify MMR re-ranking promotes diverse results."""

    async def test_mmr_diversifies_near_duplicates(
        self, integration_client: AsyncClient,
    ) -> None:
        """Low lambda penalizes near-duplicate docs for diversity."""
        # Create docs where two are near-duplicates and one is different
        store_id, _ = await _create_store_with_docs(
            integration_client, "mmr-diversity",
            docs={
                "python_v1": (
                    "Python is a versatile programming language used for web "
                    "development, data science, machine learning, and scripting."
                ),
                "python_v2": (
                    "Python is a versatile programming language "
                    "used for web development, data analysis, "
                    "artificial intelligence, and automation."
                ),
                "cooking": (
                    "Italian cuisine features fresh ingredients like tomatoes, basil, "
                    "olive oil, and mozzarella. Pasta dishes vary by region."
                ),
            },
        )

        # Search with pure relevance (lambda=1.0) — duplicates stay at the top
        pure_resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "Python programming language",
                "search_mode": "hybrid",
                "mmr_lambda": 1.0,
                "max_results": 3,
            },
        )
        # Search with diversity (lambda=0.3) — duplicates get penalized
        diverse_resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "Python programming language",
                "search_mode": "hybrid",
                "mmr_lambda": 0.3,
                "max_results": 3,
            },
        )

        assert pure_resp.status_code == 200
        assert diverse_resp.status_code == 200

        pure_results = pure_resp.json()["data"]
        diverse_results = diverse_resp.json()["data"]

        assert len(pure_results) == 3
        assert len(diverse_results) == 3

        # With diversity, the cooking doc should appear higher in the ranking
        # than with pure relevance (where the two Python docs dominate)
        diverse_contents = [r["content"] for r in diverse_results]
        pure_contents = [r["content"] for r in pure_results]

        def _cooking_rank(contents: list[str]) -> int:
            for i, c in enumerate(contents):
                if "italian" in c.lower() or "pasta" in c.lower():
                    return i
            return len(contents)

        assert _cooking_rank(diverse_contents) <= _cooking_rank(pure_contents)


# ============================================================================
# F. Ranking Weights
# ============================================================================


class TestRankingWeights:
    """Verify ranking_weights parameter affects fusion."""

    async def test_custom_weights_forwarded(
        self, integration_client: AsyncClient,
    ) -> None:
        """Custom ranking weights produce valid results."""
        store_id, _ = await _create_store_with_docs(
            integration_client, "weights-custom",
            docs={"doc": _DOCS["database_guide"]},
        )

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "PostgreSQL full-text search",
                "search_mode": "hybrid",
                "ranking_weights": {"vector": 0.3, "text": 0.7},
                "max_results": 5,
            },
        )

        assert resp.status_code == 200
        results = resp.json()["data"]
        assert len(results) >= 1
        # Results should still be valid with custom weights
        assert results[0]["score"] > 0

    async def test_both_zero_weights_rejected(
        self, integration_client: AsyncClient,
    ) -> None:
        """Both weights at zero returns 422 validation error."""
        store_id, _ = await _create_store_with_docs(
            integration_client, "weights-zero",
            docs={"doc": _DOCS["python_intro"]},
        )

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "test",
                "search_mode": "hybrid",
                "ranking_weights": {"vector": 0.0, "text": 0.0},
            },
        )

        assert resp.status_code == 422


# ============================================================================
# G. Adaptive Weight Normalization
# ============================================================================


class TestAdaptiveWeights:
    """Verify weights redistribute when one signal is absent."""

    async def test_stopword_query_still_returns_results(
        self, integration_client: AsyncClient,
    ) -> None:
        """A query of only stop words (no BM25 terms) still returns results
        via vector search with adaptive weight normalization."""
        store_id, _ = await _create_store_with_docs(
            integration_client, "adaptive-stopwords",
            docs={"doc": _DOCS["python_intro"]},
        )

        # "the a an" are all stop words — BM25 produces no terms
        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "the a an",
                "search_mode": "hybrid",
                "max_results": 5,
            },
        )

        assert resp.status_code == 200
        results = resp.json()["data"]
        # Should still get results from vector search
        assert len(results) >= 1
        # Text score should be 0 (no BM25 match), but vector score should be
        # non-zero and the overall score should be meaningful (not capped at 0.7)
        for r in results:
            assert r["score_details"]["text"] == 0.0


# ============================================================================
# H. GIN Index Verification
# ============================================================================


class TestGINIndex:
    """Verify the GIN full-text search index exists and is used."""

    async def test_gin_index_exists(self, db_session: AsyncSession) -> None:
        """The GIN index on to_tsvector('english', content) exists."""
        result = await db_session.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename = 'file_chunks' "
                "AND indexdef LIKE '%gin%'"
            )
        )
        rows = result.fetchall()
        gin_indexes = [r for r in rows if "tsvector" in (r[1] or "").lower()]
        assert len(gin_indexes) >= 1, (
            f"Expected a GIN index on to_tsvector. Found: {[r[0] for r in rows]}"
        )
