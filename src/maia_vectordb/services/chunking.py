"""Recursive text splitter with configurable chunk size and overlap."""

from __future__ import annotations

import logging

import tiktoken

from maia_vectordb.core.config import settings

logger = logging.getLogger(__name__)

# Separators tried in order: double-newline (paragraph), single-newline, space, empty
_SEPARATORS: list[str] = ["\n\n", "\n", " ", ""]

# Module-level encoding cache — avoids re-downloading tiktoken data on every call
_encoding: tiktoken.Encoding | None = None


def get_encoding() -> tiktoken.Encoding:
    """Return the cached tiktoken encoding (lazy singleton)."""
    global _encoding  # noqa: PLW0603
    if _encoding is None:
        logger.info("Loading tiktoken encoding for gpt-4o")
        _encoding = tiktoken.encoding_for_model("gpt-4o")
    return _encoding


def _token_length(text: str, encoding: tiktoken.Encoding) -> int:
    """Return the number of tokens in *text*."""
    return len(encoding.encode(text))


def split_text(
    text: str,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Split *text* into chunks respecting token limits.

    Uses a recursive strategy: try the coarsest separator first, then fall
    back to finer separators when a segment is still too large.

    Parameters
    ----------
    text:
        Plain text to split.
    chunk_size:
        Maximum tokens per chunk (default from settings).
    chunk_overlap:
        Number of overlapping tokens between consecutive chunks
        (default from settings).

    Returns
    -------
    list[str]
        Ordered list of text chunks.
    """
    if chunk_size is None:
        chunk_size = settings.chunk_size
    if chunk_overlap is None:
        chunk_overlap = settings.chunk_overlap

    encoding = get_encoding()
    return _recursive_split(text, _SEPARATORS, chunk_size, chunk_overlap, encoding)


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
    chunk_overlap: int,
    encoding: tiktoken.Encoding,
) -> list[str]:
    """Split *text* recursively using *separators* in order."""
    # Base case: text already fits in one chunk
    if _token_length(text, encoding) <= chunk_size:
        stripped = text.strip()
        return [stripped] if stripped else []

    # Pick the first separator that actually appears in the text
    separator = separators[-1]  # fallback: empty string (character-level)
    remaining_separators: list[str] = []
    for i, sep in enumerate(separators):
        if sep == "":
            separator = sep
            remaining_separators = []
            break
        if sep in text:
            separator = sep
            remaining_separators = separators[i + 1 :]
            break

    # Split on chosen separator
    if separator:
        pieces = text.split(separator)
    else:
        # Character-level split as last resort
        pieces = list(text)

    # Merge pieces into chunks that respect the token limit
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for piece in pieces:
        piece_len = _token_length(piece, encoding)
        sep_len = _token_length(separator, encoding) if current else 0

        if current and current_len + sep_len + piece_len > chunk_size:
            # Flush current into a chunk
            merged = separator.join(current)
            # If the merged chunk is still too large, recurse with finer separators
            if remaining_separators and _token_length(merged, encoding) > chunk_size:
                sub = _recursive_split(
                    merged,
                    remaining_separators,
                    chunk_size,
                    chunk_overlap,
                    encoding,
                )
                chunks.extend(sub)
            else:
                stripped = merged.strip()
                if stripped:
                    chunks.append(stripped)

            # Start new chunk with overlap from the end of the previous chunk
            current, current_len = _overlap_start(
                current, separator, chunk_overlap, encoding
            )

        current.append(piece)
        current_len += (sep_len if current_len > 0 else 0) + piece_len

    # Flush remaining
    if current:
        merged = separator.join(current)
        if remaining_separators and _token_length(merged, encoding) > chunk_size:
            sub = _recursive_split(
                merged,
                remaining_separators,
                chunk_size,
                chunk_overlap,
                encoding,
            )
            chunks.extend(sub)
        else:
            stripped = merged.strip()
            if stripped:
                chunks.append(stripped)

    return chunks


def _overlap_start(
    pieces: list[str],
    separator: str,
    overlap_tokens: int,
    encoding: tiktoken.Encoding,
) -> tuple[list[str], int]:
    """Return trailing *pieces* whose total tokens <= *overlap_tokens*."""
    result: list[str] = []
    total = 0
    for piece in reversed(pieces):
        piece_len = _token_length(piece, encoding)
        if total + piece_len > overlap_tokens:
            break
        result.insert(0, piece)
        total += piece_len
    return result, total


def read_file(path: str) -> str:
    """Read a .txt or .md file and return its text content.

    Raises
    ------
    ValueError
        If the file extension is not supported.
    """
    if not (path.endswith(".txt") or path.endswith(".md")):
        msg = f"Unsupported file type: {path!r}. Only .txt and .md."
        raise ValueError(msg)
    with open(path, encoding="utf-8") as fh:
        return fh.read()
