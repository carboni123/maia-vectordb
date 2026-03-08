"""Tests for BM25 scoring functions."""

from __future__ import annotations

import math

import pytest

from maia_vectordb.services.bm25 import bm25_score, parse_tsvector

# ---------------------------------------------------------------------------
# parse_tsvector
# ---------------------------------------------------------------------------


class TestParseTsvector:
    def test_simple_tsvector(self) -> None:
        """Standard tsvector with single positions."""
        result = parse_tsvector("'brown':3 'dog':9 'fox':4")
        assert result == {"brown": 1, "dog": 1, "fox": 1}

    def test_multiple_positions(self) -> None:
        """Term appearing at multiple positions (TF > 1)."""
        result = parse_tsvector("'cat':1,5,9 'dog':3")
        assert result == {"cat": 3, "dog": 1}

    def test_with_weight_labels(self) -> None:
        """Positions can have weight labels (A/B/C/D)."""
        result = parse_tsvector("'import':2A 'func':5B,8 'var':1C,3,7D")
        assert result == {"import": 1, "func": 2, "var": 3}

    def test_empty_string(self) -> None:
        assert parse_tsvector("") == {}

    def test_single_entry(self) -> None:
        result = parse_tsvector("'hello':1")
        assert result == {"hello": 1}


# ---------------------------------------------------------------------------
# bm25_score
# ---------------------------------------------------------------------------


class TestBM25Score:
    """Test BM25 scoring against known values."""

    # Shared corpus: 100 docs, avg length 50 tokens
    _TOTAL = 100
    _AVG_DL = 50.0

    def test_exact_match_single_term(self) -> None:
        """A document matching one query term should get a positive score."""
        score = bm25_score(
            query_terms=["fox"],
            doc_tfs={"fox": 3},
            doc_length=50,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"fox": 10},
        )
        assert score > 0

    def test_no_match_returns_zero(self) -> None:
        """A document with no matching terms scores 0."""
        score = bm25_score(
            query_terms=["fox"],
            doc_tfs={"cat": 5},
            doc_length=50,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"fox": 10},
        )
        assert score == 0.0

    def test_rare_term_scores_higher_than_common(self) -> None:
        """IDF: a rare term (low df) should contribute more than a common one."""
        rare_score = bm25_score(
            query_terms=["rare"],
            doc_tfs={"rare": 1},
            doc_length=50,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"rare": 2},  # appears in only 2 docs
        )
        common_score = bm25_score(
            query_terms=["common"],
            doc_tfs={"common": 1},
            doc_length=50,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"common": 90},  # appears in 90 docs
        )
        assert rare_score > common_score

    def test_tf_saturation(self) -> None:
        """BM25's TF saturation: doubling TF should NOT double the score."""
        score_tf1 = bm25_score(
            query_terms=["fox"],
            doc_tfs={"fox": 1},
            doc_length=50,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"fox": 10},
        )
        score_tf10 = bm25_score(
            query_terms=["fox"],
            doc_tfs={"fox": 10},
            doc_length=50,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"fox": 10},
        )
        # TF=10 should score higher than TF=1, but NOT 10× higher
        assert score_tf10 > score_tf1
        assert score_tf10 < score_tf1 * 10

    def test_shorter_doc_scores_higher(self) -> None:
        """Length normalization: shorter docs should score higher (same TF)."""
        short_score = bm25_score(
            query_terms=["fox"],
            doc_tfs={"fox": 2},
            doc_length=20,  # short doc
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"fox": 10},
        )
        long_score = bm25_score(
            query_terms=["fox"],
            doc_tfs={"fox": 2},
            doc_length=200,  # long doc
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"fox": 10},
        )
        assert short_score > long_score

    def test_multiple_query_terms(self) -> None:
        """Score for multiple query terms should be sum of individual scores."""
        combined = bm25_score(
            query_terms=["quick", "fox"],
            doc_tfs={"quick": 1, "fox": 2},
            doc_length=50,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"quick": 15, "fox": 10},
        )
        single_quick = bm25_score(
            query_terms=["quick"],
            doc_tfs={"quick": 1, "fox": 2},
            doc_length=50,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"quick": 15, "fox": 10},
        )
        single_fox = bm25_score(
            query_terms=["fox"],
            doc_tfs={"quick": 1, "fox": 2},
            doc_length=50,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"quick": 15, "fox": 10},
        )
        assert combined == pytest.approx(single_quick + single_fox)

    def test_b_zero_disables_length_norm(self) -> None:
        """With b=0, document length should not affect the score."""
        short = bm25_score(
            query_terms=["fox"],
            doc_tfs={"fox": 1},
            doc_length=10,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"fox": 10},
            b=0.0,
        )
        long = bm25_score(
            query_terms=["fox"],
            doc_tfs={"fox": 1},
            doc_length=500,
            total_docs=self._TOTAL,
            avg_dl=self._AVG_DL,
            doc_freqs={"fox": 10},
            b=0.0,
        )
        assert short == pytest.approx(long)

    def test_known_value(self) -> None:
        """Verify against a hand-calculated BM25 score."""
        # Single term: "fox", tf=2, dl=50, N=100, df=10, k1=1.2, b=0.75
        # IDF = ln((100-10+0.5)/(10+0.5) + 1) = ln(9.619) ≈ 2.2638
        # TF_norm = (2 * 2.2) / (2 + 1.2 * (1 - 0.75 + 0.75 * 50/50))
        #         = 4.4 / (2 + 1.2 * 1.0) = 4.4 / 3.2 = 1.375
        # score = 2.2638 * 1.375 ≈ 3.1128
        idf = math.log((100 - 10 + 0.5) / (10 + 0.5) + 1.0)
        tf_norm = (2 * (1.2 + 1)) / (2 + 1.2 * (1 - 0.75 + 0.75 * 50 / 50))
        expected = idf * tf_norm

        score = bm25_score(
            query_terms=["fox"],
            doc_tfs={"fox": 2},
            doc_length=50,
            total_docs=100,
            avg_dl=50.0,
            doc_freqs={"fox": 10},
        )
        assert score == pytest.approx(expected, rel=1e-6)

    def test_zero_avg_dl_safe(self) -> None:
        """avg_dl=0 should not cause division by zero."""
        score = bm25_score(
            query_terms=["fox"],
            doc_tfs={"fox": 1},
            doc_length=50,
            total_docs=10,
            avg_dl=0.0,
            doc_freqs={"fox": 5},
        )
        assert score > 0
        assert math.isfinite(score)
