"""Async engine and session factory.

A single engine/session factory per process, created lazily from settings.
M2 will reuse `get_db_session` as the FastAPI dependency.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def _engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(_engine(), expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session per request (FastAPI dependency)."""
    async with _session_factory() as session:
        yield session


async def dispose_engine() -> None:
    """Close pooled connections (app shutdown)."""
    _engine().dispose()
    _engine.cache_clear()
    _session_factory.cache_clear()
