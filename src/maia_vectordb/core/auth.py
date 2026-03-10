"""API key authentication dependency."""

from __future__ import annotations

from fastapi import Security
from fastapi.security import APIKeyHeader

from maia_vectordb.core.config import settings
from maia_vectordb.core.exceptions import AuthenticationError

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """Validate the X-API-Key request header against configured API keys.

    Raises :class:`AuthenticationError` when the header is absent or the
    key is not in ``settings.api_keys``.  Returns the validated key on
    success.
    """
    if not api_key or api_key not in settings.api_keys:
        raise AuthenticationError()
    return api_key
