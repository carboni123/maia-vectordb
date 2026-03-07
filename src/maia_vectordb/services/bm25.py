"""BM25 (Best Matching 25) scoring for full-text search ranking.

Implements the Okapi BM25 formula used by Elasticsearch, Lucene, and most
modern search engines.  PostgreSQL's built-in ``ts_rank_cd`` is a cover
density measure that lacks TF saturation and document-length normalization
— this module provides a proper BM25 alternative.

Usage:
    Parse a PostgreSQL tsvector string into term frequencies, then compute
    the BM25 score given corpus-level statistics.
"""

from __future__ import annotations

import math
import re

# Matches each entry in a PostgreSQL tsvector string representation.
# Example input: "'brown':3 'dog':9 'fox':4A,7 'jump':5B,8"
# Group 1 = lexeme, Group 2 = position string (e.g. "4A,7")
_TSVECTOR_ENTRY_RE = re.compile(r"'([^']+)':(\S+)")

# Default BM25 parameters (same as Elasticsearch / Lucene defaults)
DEFAULT_K1 = 1.2
DEFAULT_B = 0.75


def parse_tsvector(tsvector_str: str) -> dict[str, int]:
    """Parse a PostgreSQL tsvector string into ``{lexeme: term_frequency}``.

    PostgreSQL represents tsvectors as e.g.::

        'brown':3 'dog':9 'fox':4,7 'jump':5

    Each comma-separated position counts as one occurrence, giving the
    term frequency for that lexeme in the document.
    """
    result: dict[str, int] = {}
    for m in _TSVECTOR_ENTRY_RE.finditer(tsvector_str):
        lexeme = m.group(1)
        positions = m.group(2)
        # Each position is separated by comma; count = TF
        tf = positions.count(",") + 1
        result[lexeme] = tf
    return result


def bm25_score(
    query_terms: list[str],
    doc_tfs: dict[str, int],
    doc_length: int,
    total_docs: int,
    avg_dl: float,
    doc_freqs: dict[str, int],
    k1: float = DEFAULT_K1,
    b: float = DEFAULT_B,
) -> float:
    """Compute BM25 score for a single document.

    Parameters
    ----------
    query_terms:
        Stemmed query lexemes (from ``to_tsvector('english', query)``).
    doc_tfs:
        Term frequencies in this document (from :func:`parse_tsvector`).
    doc_length:
        Document length in tokens (``file_chunks.token_count``).
    total_docs:
        Total number of documents in the corpus (vector store).
    avg_dl:
        Average document length across the corpus.
    doc_freqs:
        ``{term: n_docs_containing_term}`` for each query term.
    k1:
        Controls TF saturation. Higher = less saturation. Default 1.2.
    b:
        Controls document length normalization. 0 = no normalization,
        1 = full normalization. Default 0.75.

    Returns
    -------
    float
        BM25 relevance score (non-negative, unbounded).
    """
    score = 0.0
    safe_avg_dl = avg_dl if avg_dl > 0 else 1.0

    for term in query_terms:
        tf = doc_tfs.get(term, 0)
        if tf == 0:
            continue

        df = doc_freqs.get(term, 0)

        # IDF: Robertson–Spärck Jones formula (non-negative variant)
        idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)

        # TF saturation with document length normalization
        tf_component = (tf * (k1 + 1.0)) / (
            tf + k1 * (1.0 - b + b * doc_length / safe_avg_dl)
        )

        score += idf * tf_component

    return score
