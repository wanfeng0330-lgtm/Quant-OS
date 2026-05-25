"""Celery tasks for data synchronization."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from quant_os_shared.config.settings import get_settings
from quant_os_infra_market.providers import ProviderFactory

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create async engine for tasks
engine = create_async_engine(
    settings.database.async_url,
    pool_size=5,
    max_overflow=5,
    echo=False,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_stock_list(self) -> dict[str, Any]:
    """Sync the complete A-share stock list.
    
    Returns:
        Dictionary with sync results
    """
    import asyncio
    
    async def _sync_stock_list():
        async with async_session() as session:
            try:
                # Get data provider
                provider = ProviderFactory.get()
                
                # Import data ingestion service
                from quant_os_app_market.services.data_ingestion import (
                    DataIngestionService,
                )
                
                # Create service
                service = DataIngestionService(
                    session=session,
                    provider=provider,
                )
                
                # Sync stock list
                result = await service.sync_stock_list()
                
                # Commit changes
                await session.commit()
                
                return {
                    "status": "success",
                    "task": "sync_stock_list",
                    "result": result,
                    "synced_at": datetime.now().isoformat(),
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(
                    "Stock list sync failed: %s",
                    e, exc_info=True,
                )
                raise
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_sync_stock_list())
        return result
    except Exception as e:
        logger.error("Stock list sync task failed: %s", e, exc_info=True)
        # Retry on failure
        raise self.retry(exc=e)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_daily_ohlcv(self, trade_date: str | None = None) -> dict[str, Any]:
    """Sync daily OHLCV data for all stocks.
    
    Args:
        trade_date: Optional trade date in YYYY-MM-DD format.
                   If not provided, uses today's date.
    
    Returns:
        Dictionary with sync results
    """
    import asyncio
    
    async def _sync_daily_ohlcv():
        async with async_session() as session:
            try:
                # Parse trade date
                if trade_date:
                    target_date = date.fromisoformat(trade_date)
                else:
                    target_date = date.today()
                
                # Get data provider
                provider = ProviderFactory.get()
                
                # Import data ingestion service
                from quant_os_app_market.services.data_ingestion import (
                    DataIngestionService,
                )
                
                # Create service
                service = DataIngestionService(
                    session=session,
                    provider=provider,
                )
                
                # Sync OHLCV data
                result = await service.sync_ohlcv_all_stocks(target_date)
                
                # Commit changes
                await session.commit()
                
                return {
                    "status": "success",
                    "task": "sync_daily_ohlcv",
                    "trade_date": str(target_date),
                    "result": result,
                    "synced_at": datetime.now().isoformat(),
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(
                    "Daily OHLCV sync failed: %s",
                    e, exc_info=True,
                )
                raise
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_sync_daily_ohlcv())
        return result
    except Exception as e:
        logger.error("Daily OHLCV sync task failed: %s", e, exc_info=True)
        # Retry on failure
        raise self.retry(exc=e)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_ohlcv_daily_for_stock(
    self,
    ts_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Sync daily OHLCV data for a specific stock.
    
    Args:
        ts_code: Stock code (e.g., "000001.SZ")
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format
    
    Returns:
        Dictionary with sync results
    """
    import asyncio
    
    async def _sync_stock_ohlcv():
        async with async_session() as session:
            try:
                # Parse dates
                start = date.fromisoformat(start_date) if start_date else None
                end = date.fromisoformat(end_date) if end_date else None
                
                # Get data provider
                provider = ProviderFactory.get()
                
                # Import data ingestion service
                from quant_os_app_market.services.data_ingestion import (
                    DataIngestionService,
                )
                
                # Create service
                service = DataIngestionService(
                    session=session,
                    provider=provider,
                )
                
                # Sync OHLCV data
                result = await service.sync_ohlcv_daily(
                    ts_code=ts_code,
                    start_date=start,
                    end_date=end,
                )
                
                # Commit changes
                await session.commit()
                
                return {
                    "status": "success",
                    "task": "sync_ohlcv_daily_for_stock",
                    "ts_code": ts_code,
                    "result": result,
                    "synced_at": datetime.now().isoformat(),
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(
                    "OHLCV sync failed for %s: %s",
                    ts_code, e, exc_info=True,
                )
                raise
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_sync_stock_ohlcv())
        return result
    except Exception as e:
        logger.error(
            "OHLCV sync task failed for %s: %s",
            ts_code, e, exc_info=True,
        )
        # Retry on failure
        raise self.retry(exc=e)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_trading_calendar(self, year: int | None = None) -> dict[str, Any]:
    """Sync trading calendar for a specific year.
    
    Args:
        year: Optional year to sync. If not provided, uses current year.
    
    Returns:
        Dictionary with sync results
    """
    import asyncio
    
    async def _sync_trading_calendar():
        async with async_session() as session:
            try:
                # Use current year if not provided
                target_year = year or datetime.now().year
                
                # Get data provider
                provider = ProviderFactory.get()
                
                # Import data ingestion service
                from quant_os_app_market.services.data_ingestion import (
                    DataIngestionService,
                )
                
                # Create service
                service = DataIngestionService(
                    session=session,
                    provider=provider,
                )
                
                # Sync trading calendar
                result = await service.sync_trading_calendar(year=target_year)
                
                # Commit changes
                await session.commit()
                
                return {
                    "status": "success",
                    "task": "sync_trading_calendar",
                    "year": target_year,
                    "result": result,
                    "synced_at": datetime.now().isoformat(),
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(
                    "Trading calendar sync failed for %d: %s",
                    target_year, e, exc_info=True,
                )
                raise
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_sync_trading_calendar())
        return result
    except Exception as e:
        logger.error("Trading calendar sync task failed: %s", e, exc_info=True)
        # Retry on failure
        raise self.retry(exc=e)
    finally:
        loop.close()