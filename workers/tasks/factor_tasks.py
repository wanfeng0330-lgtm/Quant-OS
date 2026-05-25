"""Celery tasks for factor computation."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from quant_os_shared.config.settings import get_settings
from quant_os_infra_factor.repositories.factor_repo import FactorRepository
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
def compute_factor_task(
    self,
    factor_id: str,
    start_date: str,
    end_date: str,
    stock_pool: list[str] | None = None,
) -> dict[str, Any]:
    """Compute factor values and run analysis.
    
    Args:
        factor_id: Factor ID to compute
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        stock_pool: Optional list of stock codes
        
    Returns:
        Dictionary with computation results
    """
    import asyncio
    
    async def _compute_factor():
        async with async_session() as session:
            try:
                # Get factor from database
                factor_repo = FactorRepository(session)
                factor = await factor_repo.get_by_id(factor_id)
                
                if not factor:
                    return {
                        "status": "error",
                        "message": f"Factor {factor_id} not found",
                    }
                
                # Get data provider
                provider = ProviderFactory.get()
                
                # Import and create factor compute service
                from quant_os_app_factor.services.factor_compute_service import (
                    FactorComputeService,
                )
                from quant_os_domain_factor.entities.factor import (
                    FactorDefinition, FactorCategory, FactorDirection,
                )
                
                # Create factor definition
                factor_def = FactorDefinition(
                    factor_name=factor.factor_name,
                    display_name=factor.display_name or factor.factor_name,
                    category=FactorCategory(factor.category),
                    description=factor.description or "",
                    formula=factor.formula or "",
                    direction=FactorDirection(factor.direction),
                    params=factor.params or {},
                )
                
                # Create service
                service = FactorComputeService(
                    session=session,
                    provider=provider,
                )
                
                # Parse dates
                start = date.fromisoformat(start_date)
                end = date.fromisoformat(end_date)
                
                # Compute factor values
                factor_values = await service.compute_factor_values(
                    factor_def=factor_def,
                    start_date=start,
                    end_date=end,
                    stock_pool=stock_pool,
                    factor_id=factor_id,
                    store_to_db=True,
                )
                
                # Run analysis
                analysis_result = await service.analyze_factor(
                    factor_id=factor_id,
                    start_date=start,
                    end_date=end,
                )
                
                # Commit changes
                await session.commit()
                
                return {
                    "status": "success",
                    "factor_id": factor_id,
                    "factor_name": factor.factor_name,
                    "values_computed": len(factor_values),
                    "analysis": analysis_result,
                    "computed_at": datetime.now().isoformat(),
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(
                    "Factor computation failed for %s: %s",
                    factor_id, e, exc_info=True,
                )
                raise
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_compute_factor())
        return result
    except Exception as e:
        logger.error("Factor task failed: %s", e, exc_info=True)
        # Retry on failure
        raise self.retry(exc=e)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def compute_active_factors(self) -> dict[str, Any]:
    """Compute all active factors.
    
    This task is typically scheduled to run daily after data sync.
    
    Returns:
        Dictionary with computation results for all factors
    """
    import asyncio
    
    async def _compute_active_factors():
        async with async_session() as session:
            try:
                # Get all active factors
                factor_repo = FactorRepository(session)
                factors = await factor_repo.list_factors(is_active=True)
                
                if not factors:
                    return {
                        "status": "success",
                        "message": "No active factors to compute",
                        "computed": 0,
                    }
                
                # Get data provider
                provider = ProviderFactory.get()
                
                # Import factor compute service
                from quant_os_app_factor.services.factor_compute_service import (
                    FactorComputeService,
                )
                from quant_os_domain_factor.entities.factor import (
                    FactorDefinition, FactorCategory, FactorDirection,
                )
                
                # Create service
                service = FactorComputeService(
                    session=session,
                    provider=provider,
                )
                
                # Compute for last 1 year
                end_date = date.today()
                start_date = end_date - timedelta(days=365)
                
                results = []
                for factor in factors:
                    try:
                        # Create factor definition
                        factor_def = FactorDefinition(
                            factor_name=factor.factor_name,
                            display_name=factor.display_name or factor.factor_name,
                            category=FactorCategory(factor.category),
                            description=factor.description or "",
                            formula=factor.formula or "",
                            direction=FactorDirection(factor.direction),
                            params=factor.params or {},
                        )
                        
                        # Compute factor values
                        factor_values = await service.compute_factor_values(
                            factor_def=factor_def,
                            start_date=start_date,
                            end_date=end_date,
                            factor_id=factor.id,
                            store_to_db=True,
                        )
                        
                        # Run analysis
                        analysis_result = await service.analyze_factor(
                            factor_id=factor.id,
                            start_date=start_date,
                            end_date=end_date,
                        )
                        
                        results.append({
                            "factor_id": factor.id,
                            "factor_name": factor.factor_name,
                            "status": "success",
                            "values_computed": len(factor_values),
                            "analysis": analysis_result,
                        })
                        
                    except Exception as e:
                        logger.error(
                            "Failed to compute factor %s: %s",
                            factor.factor_name, e, exc_info=True,
                        )
                        results.append({
                            "factor_id": factor.id,
                            "factor_name": factor.factor_name,
                            "status": "error",
                            "error": str(e),
                        })
                
                # Commit all changes
                await session.commit()
                
                # Count successes and failures
                successes = sum(1 for r in results if r["status"] == "success")
                failures = len(results) - successes
                
                return {
                    "status": "success",
                    "total_factors": len(factors),
                    "successes": successes,
                    "failures": failures,
                    "results": results,
                    "computed_at": datetime.now().isoformat(),
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(
                    "Active factors computation failed: %s",
                    e, exc_info=True,
                )
                raise
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_compute_active_factors())
        return result
    except Exception as e:
        logger.error("Active factors task failed: %s", e, exc_info=True)
        # Retry on failure
        raise self.retry(exc=e)
    finally:
        loop.close()