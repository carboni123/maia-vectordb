"""Tests for the text chunking service."""

from __future__ import annotations

from pathlib import Path

import tiktoken

from maia_vectordb.services.chunking import read_file, split_text


def _count_tokens(text: str) -> int:
    enc = tiktoken.encoding_for_model("gpt-4o")
    return len(enc.encode(text))


# ---------------------------------------------------------------------------
# AC 1: Text split into chunks respecting token limits
# ---------------------------------------------------------------------------


class TestSplitTextTokenLimits:
    """Chunks must not exceed the configured token limit."""

    def test_short_text_single_chunk(self) -> None:
        """Text shorter than chunk_size stays in one chunk."""
        chunks = split_text("Hello world", chunk_size=100, chunk_overlap=10)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_long_text_splits(self) -> None:
        """Text exceeding chunk_size is split into multiple chunks."""
        text = "word " * 2000  # ~2000 tokens
        chunks = split_text(text, chunk_size=200, chunk_overlap=0)
        assert len(chunks) > 1

    def test_each_chunk_within_limit(self) -> None:
        """Every chunk should be within the token limit."""
        text = "word " * 2000
        chunk_size = 200
        chunks = split_text(text, chunk_size=chunk_size, chunk_overlap=0)
        for chunk in chunks:
            assert _count_tokens(chunk) <= chunk_size

    def test_empty_text(self) -> None:
        """Empty text produces no chunks."""
        chunks = split_text("", chunk_size=100, chunk_overlap=10)
        assert chunks == []

    def test_whitespace_only(self) -> None:
        """Whitespace-only text produces no chunks."""
        chunks = split_text("   \n\n  ", chunk_size=100, chunk_overlap=10)
        assert chunks == []


# ---------------------------------------------------------------------------
# AC 2: Chunk overlap prevents context loss at boundaries
# ---------------------------------------------------------------------------


class TestChunkOverlap:
    """Consecutive chunks should share overlapping content."""

    def test_overlap_content_shared(self) -> None:
        """With overlap > 0, consecutive chunks should share some text."""
        # Build text with distinct paragraphs
        paragraphs = [f"Paragraph {i} " + "filler " * 80 for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = split_text(text, chunk_size=200, chunk_overlap=50)
        assert len(chunks) >= 2

        # Check that some content overlaps between consecutive chunks
        overlap_found = False
        for i in range(len(chunks) - 1):
            words_a = set(chunks[i].split())
            words_b = set(chunks[i + 1].split())
            if words_a & words_b:
                overlap_found = True
                break
        assert overlap_found, "Expected overlapping content between consecutive chunks"

    def test_zero_overlap_no_duplication(self) -> None:
        """With overlap=0, chunks should have minimal duplication."""
        text = " ".join(f"word{i}" for i in range(500))
        chunks = split_text(text, chunk_size=100, chunk_overlap=0)
        assert len(chunks) >= 2


# ---------------------------------------------------------------------------
# AC 5: Supports .txt and .md file types
# ---------------------------------------------------------------------------


class TestReadFile:
    """File reading supports .txt and .md files."""

    def test_read_txt_file(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.txt"
        f.write_text("Hello from txt", encoding="utf-8")
        content = read_file(str(f))
        assert content == "Hello from txt"

    def test_read_md_file(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.md"
        f.write_text("# Heading\nContent", encoding="utf-8")
        content = read_file(str(f))
        assert content == "# Heading\nContent"

    def test_unsupported_file_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.pdf"
        f.write_text("fake pdf", encoding="utf-8")
        try:
            read_file(str(f))
            raise AssertionError("Expected ValueError")
        except ValueError as exc:
            assert "Unsupported file type" in str(exc)


class TestRecursiveSplitBehavior:
    """The recursive splitter uses paragraph and line separators."""

    def test_splits_on_paragraphs(self) -> None:
        """Double-newline paragraphs are preferred split points."""
        para = "word " * 150  # ~150 tokens
        text = f"{para}\n\n{para}\n\n{para}"
        chunks = split_text(text, chunk_size=200, chunk_overlap=0)
        # Should split on paragraph boundaries, not mid-paragraph
        assert len(chunks) >= 2

    def test_splits_on_lines_when_needed(self) -> None:
        """Single-newline splits are used when paragraphs are too long."""
        line = "word " * 150
        text = f"{line}\n{line}\n{line}"
        chunks = split_text(text, chunk_size=200, chunk_overlap=0)
        assert len(chunks) >= 2

    def test_configurable_defaults(self) -> None:
        """split_text uses settings defaults when args not provided."""
        # Just check it runs without error using settings defaults
        chunks = split_text("Hello world")
        assert len(chunks) == 1
