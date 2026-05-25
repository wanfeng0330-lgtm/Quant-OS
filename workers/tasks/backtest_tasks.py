"""Celery tasks for backtest execution."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from quant_os_shared.config.settings import get_settings

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


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def run_backtest_task(
    self,
    backtest_run_id: str,
) -> dict[str, Any]:
    """Execute a backtest run.
    
    Args:
        backtest_run_id: Backtest run ID to execute
        
    Returns:
        Dictionary with backtest results
    """
    import asyncio
    
    async def _run_backtest():
        async with async_session() as session:
            try:
                # Get data provider
                from quant_os_infra_market.providers import ProviderFactory
                provider = ProviderFactory.get()
                
                # Import backtest service
                from quant_os_app_backtest.services.backtest_service import (
                    BacktestService,
                )
                
                # Create service
                service = BacktestService(
                    session=session,
                    provider=provider,
                )
                
                # Execute backtest
                result = await service.execute_backtest(backtest_run_id)
                
                return {
                    "status": "success",
                    "backtest_run_id": backtest_run_id,
                    "result": result.to_dict(),
                    "completed_at": datetime.now().isoformat(),
                }
                
            except Exception as e:
                logger.error(
                    "Backtest execution failed for %s: %s",
                    backtest_run_id, e, exc_info=True,
                )
                raise
    
    # Run async function using asyncio.run() to avoid event loop leakage
    try:
        result = asyncio.run(_run_backtest())
        return result
    except Exception as e:
        logger.error(
            "Backtest task failed for %s: %s",
            backtest_run_id, e, exc_info=True,
        )
        # Retry on failure
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def cancel_backtest_task(
    self,
    backtest_run_id: str,
) -> dict[str, Any]:
    """Cancel a running backtest.
    
    Args:
        backtest_run_id: Backtest run ID to cancel
        
    Returns:
        Dictionary with cancellation results
    """
    import asyncio
    
    async def _cancel_backtest():
        async with async_session() as session:
            try:
                # Get data provider
                from quant_os_infra_market.providers import ProviderFactory
                provider = ProviderFactory.get()
                
                # Import backtest service
                from quant_os_app_backtest.services.backtest_service import (
                    BacktestService,
                )
                
                # Create service
                service = BacktestService(
                    session=session,
                    provider=provider,
                )
                
                # Cancel backtest
                success = await service.cancel_backtest_run(backtest_run_id)
                
                if success:
                    return {
                        "status": "success",
                        "backtest_run_id": backtest_run_id,
                        "message": "Backtest cancelled successfully",
                        "cancelled_at": datetime.now().isoformat(),
                    }
                else:
                    return {
                        "status": "error",
                        "backtest_run_id": backtest_run_id,
                        "message": "Cannot cancel backtest (not found or not cancellable)",
                    }
                
            except Exception as e:
                logger.error(
                    "Backtest cancellation failed for %s: %s",
                    backtest_run_id, e, exc_info=True,
                )
                raise
    
    # Run async function using asyncio.run() to avoid event loop leakage
    try:
        result = asyncio.run(_cancel_backtest())
        return result
    except Exception as e:
        logger.error(
            "Backtest cancellation task failed for %s: %s",
            backtest_run_id, e, exc_info=True,
        )
        # Retry on failure
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=1, default_retry_delay=300)
def run_backtest_with_strategy_task(
    self,
    strategy_id: str,
    start_date: str,
    end_date: str,
    benchmark_code: str = "000300.SH",
    initial_capital: float = 1000000.0,
    commission_rate: float = 0.0003,
    slippage_rate: float = 0.001,
) -> dict[str, Any]:
    """Create and execute a backtest run.
    
    Args:
        strategy_id: Strategy ID to backtest
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        benchmark_code: Benchmark index code
        initial_capital: Initial capital amount
        commission_rate: Commission rate
        slippage_rate: Slippage rate
        
    Returns:
        Dictionary with backtest results
    """
    import asyncio
    from decimal import Decimal
    
    async def _run_backtest_with_strategy():
        async with async_session() as session:
            try:
                # Get data provider
                from quant_os_infra_market.providers import ProviderFactory
                provider = ProviderFactory.get()
                
                # Import backtest service
                from quant_os_app_backtest.services.backtest_service import (
                    BacktestService,
                )
                
                # Create service
                service = BacktestService(
                    session=session,
                    provider=provider,
                )
                
                # Parse dates
                start = date.fromisoformat(start_date)
                end = date.fromisoformat(end_date)
                
                # Create backtest run
                backtest_run = await service.create_backtest_run(
                    strategy_id=strategy_id,
                    start_date=start,
                    end_date=end,
                    benchmark_code=benchmark_code,
                    initial_capital=Decimal(str(initial_capital)),
                    commission_rate=Decimal(str(commission_rate)),
                    slippage_rate=Decimal(str(slippage_rate)),
                )
                
                # Execute backtest
                result = await service.execute_backtest(backtest_run.id)
                
                return {
                    "status": "success",
                    "backtest_run_id": backtest_run.id,
                    "strategy_id": strategy_id,
                    "result": result.to_dict(),
                    "completed_at": datetime.now().isoformat(),
                }
                
            except Exception as e:
                logger.error(
                    "Backtest with strategy failed for %s: %s",
                    strategy_id, e, exc_info=True,
                )
                raise
    
    # Run async function using asyncio.run() to avoid event loop leakage
    try:
        result = asyncio.run(_run_backtest_with_strategy())
        return result
    except Exception as e:
        logger.error(
            "Backtest with strategy task failed for %s: %s",
            strategy_id, e, exc_info=True,
        )
        # Retry on failure
        raise self.retry(exc=e)