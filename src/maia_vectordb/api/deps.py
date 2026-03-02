"""Shared FastAPI dependency annotations for API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.db.engine import get_db_session

DBSession = Annotated[AsyncSession, Depends(get_db_session)]
