"""Text extraction service for binary file formats (PDF, DOCX)."""

from __future__ import annotations

from maia_vectordb.core.exceptions import ValidationError

_TEXT_EXTENSIONS = frozenset(
    {".txt", ".md", ".json", ".html", ".htm", ".csv", ".xml", ".yaml", ".yml"}
)

_BINARY_EXTENSIONS = frozenset({".pdf", ".docx"})

_SUPPORTED_EXTENSIONS = _TEXT_EXTENSIONS | _BINARY_EXTENSIONS


def detect_file_type(filename: str) -> str:
    """Return the lowercased extension for *filename*.

    Raises ``ValidationError`` for unsupported formats.
    """
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        ext = ".txt"  # default for extensionless files
    else:
        ext = filename[dot_idx:].lower()

    if ext not in _SUPPORTED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file format '{ext}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
        )
    return ext


def is_binary_format(ext: str) -> bool:
    """Return True if *ext* is a binary format that needs special parsing."""
    return ext in _BINARY_EXTENSIONS


def extract_text(raw: bytes, ext: str) -> str:
    """Extract plain text from binary file bytes.

    Dispatches to format-specific extractors based on *ext*.
    """
    if ext == ".pdf":
        return _extract_pdf(raw)
    if ext == ".docx":
        return _extract_docx(raw)
    raise ValidationError(f"No extractor for format '{ext}'")


def _extract_pdf(raw: bytes) -> str:
    """Extract text from a PDF using PyMuPDF (fitz)."""
    import fitz  # lazy import

    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:
        raise ValidationError(
            "Failed to parse PDF file. The file may be corrupt or password-protected."
        ) from exc

    pages = []
    try:
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text.strip())
    finally:
        doc.close()

    if not pages:
        raise ValidationError("PDF document contains no extractable text.")
    return "\n\n".join(pages)


def _extract_docx(raw: bytes) -> str:
    """Extract text from a DOCX using python-docx."""
    import io

    import docx  # lazy import

    try:
        doc = docx.Document(io.BytesIO(raw))
    except Exception as exc:
        raise ValidationError(
            "Failed to parse DOCX file. The file may be corrupt or "
            "not a valid DOCX document."
        ) from exc

    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

    if not paragraphs:
        raise ValidationError("DOCX document contains no extractable text.")
    return "\n\n".join(paragraphs)
