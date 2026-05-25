"""FastAPI dependency injection."""

from __future__ import annotations

import asyncio
import structlog
from functools import lru_cache
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import get_app_settings
from quant_os_shared.config.settings import Settings
from quant_os_shared.events.bus import EventBus

logger = structlog.get_logger("api.db")


@lru_cache
def get_settings_cached() -> Settings:
    return get_app_settings()


_engine = None
_session_factory = None
_db_initialized = False
_db_init_lock = asyncio.Lock()


def get_engine():
    global _engine
    if _engine is None:
        settings = get_app_settings()
        connect_args = {}
        engine_kwargs = {
            "echo": settings.app.debug,
        }

        if settings.database.is_sqlite:
            # SQLite doesn't support connection pooling
            connect_args["check_same_thread"] = False
            logger.info("Using SQLite database", url=settings.database.async_url)
        else:
            engine_kwargs["pool_size"] = settings.database.pool_size
            engine_kwargs["max_overflow"] = settings.database.max_overflow
            logger.info("Using PostgreSQL database", host=settings.database.host)

        _engine = create_async_engine(
            settings.database.async_url,
            connect_args=connect_args,
            **engine_kwargs,
        )
    return _engine


async def init_database() -> None:
    """Initialize database tables for SQLite (auto-create)."""
    global _db_initialized
    if _db_initialized:
        return

    async with _db_init_lock:
        if _db_initialized:
            return

        settings = get_app_settings()
        if not settings.database.is_sqlite:
            _db_initialized = True
            return

        engine = get_engine()

        # Import all models to register them with Base.metadata.
        from quant_os_infra_market.models.base import Base
        import quant_os_infra_market.models.stock_model
        import quant_os_infra_market.models.ohlcv_model
        import quant_os_infra_market.models.sector_model
        import quant_os_infra_market.models.financial_model
        import quant_os_infra_market.models.announcement_model
        import quant_os_infra_market.models.dragon_tiger_model
        import quant_os_infra_market.models.northbound_model
        import quant_os_infra_market.models.calendar_model
        import quant_os_infra_factor.models.factor_model
        import quant_os_infra_strategy.models.strategy_model
        import quant_os_infra_agent.models.agent_model

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("SQLite database tables created")
        _db_initialized = True


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    await init_database()
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
