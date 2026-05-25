"""Shared database session factory for non-FastAPI contexts (agents, workers)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        from quant_os_shared.config.settings import get_settings
        settings = get_settings()
        connect_args = {}
        kwargs = {"echo": False}
        if settings.database.is_sqlite:
            connect_args["check_same_thread"] = False
        else:
            kwargs["pool_size"] = 5
            kwargs["max_overflow"] = 3
        _engine = create_async_engine(
            settings.database.async_url,
            connect_args=connect_args,
            **kwargs,
        )
        logger.info("Created database engine for session helper")
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for use outside FastAPI (agent tools, workers)."""
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
