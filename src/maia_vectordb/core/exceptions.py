"""Custom exception hierarchy for the MAIA VectorDB API."""

from __future__ import annotations


class APIError(Exception):
    """Base exception for all API errors.

    Subclasses set ``status_code`` and ``error_type`` so the global handler
    can build a consistent JSON response.
    """

    status_code: int = 500
    error_type: str = "api_error"

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(APIError):
    """Raised when a requested resource does not exist."""

    status_code: int = 404
    error_type: str = "not_found"

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message)


class ValidationError(APIError):
    """Raised when request input fails validation."""

    status_code: int = 400
    error_type: str = "validation_error"

    def __init__(self, message: str = "Invalid request") -> None:
        super().__init__(message)


class EmbeddingServiceError(APIError):
    """Raised when the embedding service (OpenAI) is unavailable or fails."""

    status_code: int = 502
    error_type: str = "embedding_service_error"

    def __init__(self, message: str = "Embedding service unavailable") -> None:
        super().__init__(message)


class DatabaseError(APIError):
    """Raised when a database operation fails."""

    status_code: int = 503
    error_type: str = "database_error"

    def __init__(self, message: str = "Database error") -> None:
        super().__init__(message)


class FileTooLargeError(APIError):
    """Raised when an uploaded file exceeds the configured size limit."""

    status_code: int = 413
    error_type: str = "file_too_large"

    def __init__(self, message: str = "File exceeds maximum allowed size") -> None:
        super().__init__(message)


class RateLimitError(APIError):
    """Raised when a client exceeds the configured request rate limit."""

    status_code: int = 429
    error_type: str = "rate_limit_exceeded"

    def __init__(self, message: str = "Rate limit exceeded. Please slow down.") -> None:
        super().__init__(message)
