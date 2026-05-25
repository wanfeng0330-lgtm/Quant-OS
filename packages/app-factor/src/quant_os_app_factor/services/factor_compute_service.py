"""Factor computation service - orchestrates factor calculation and analysis."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_domain_factor.services.analyzer import FactorAnalyzer, ICResult, LayeredBacktestResult
from quant_os_domain_factor.entities.factor import FactorDefinition
from quant_os_infra_factor.repositories.factor_repo import FactorRepository
from quant_os_infra_factor.repositories.factor_value_repo import FactorValueRepository
from quant_os_infra_market.providers.base import DataProvider
from quant_os_infra_market.repositories.ohlcv_repo import OHLCVRepository
from quant_os_shared.errors import FactorComputeError, DataNotFoundError

logger = logging.getLogger(__name__)


class FactorComputeService:
    """Orchestrates factor computation, analysis, and storage."""

    def __init__(
        self,
        session: AsyncSession,
        provider: DataProvider,
    ) -> None:
        self._session = session
        self._provider = provider
        self._factor_repo = FactorRepository(session)
        self._factor_value_repo = FactorValueRepository(session)
        self._ohlcv_repo = OHLCVRepository(session)
        self._analyzer = FactorAnalyzer()

    async def compute_factor_values(
        self,
        factor_def: FactorDefinition,
        start_date: date,
        end_date: date,
        stock_pool: list[str] | None = None,
        factor_id: str | None = None,
        store_to_db: bool = False,
    ) -> pd.DataFrame:
        """Compute factor values for given date range.
        
        Args:
            factor_def: Factor definition from domain layer
            start_date: Start date for computation
            end_date: End date for computation
            stock_pool: Optional list of stock codes to restrict computation
            factor_id: Optional factor ID for storing values in database
            store_to_db: Whether to store computed values to database
            
        Returns:
            DataFrame with columns [ts_code, trade_date, value]
        """
        logger.info(
            "Computing factor %s from %s to %s",
            factor_def.factor_name, start_date, end_date,
        )

        # Fetch market data from provider
        market_data = await self._fetch_market_data(
            start_date, end_date, stock_pool
        )
        
        if market_data.empty:
            raise DataNotFoundError(
                f"No market data available for {start_date} to {end_date}"
            )

        # Compute factor values using domain logic
        # This is a placeholder - actual factor computation depends on factor type
        factor_values = self._calculate_factor_values(
            factor_def, market_data
        )
        
        logger.info(
            "Computed %d factor values for %s",
            len(factor_values), factor_def.factor_name,
        )
        
        # Store to database if requested
        if store_to_db and factor_id and not factor_values.empty:
            try:
                # Prepare records for storage
                records = []
                for _, row in factor_values.iterrows():
                    record = {
                        "ts_code": row["ts_code"],
                        "trade_date": row["trade_date"],
                        "factor_id": factor_id,
                        "value": float(row["value"]) if pd.notna(row["value"]) else None,
                    }
                    records.append(record)
                
                # Delete existing values for this date range
                await self._factor_value_repo.delete_by_factor_and_date_range(
                    factor_id, start_date, end_date
                )
                
                # Insert new values
                inserted = await self._factor_value_repo.bulk_insert(records)
                logger.info(
                    "Stored %d factor values for %s to database",
                    inserted, factor_def.factor_name,
                )
            except Exception as e:
                logger.error(
                    "Failed to store factor values: %s", e,
                    exc_info=True,
                )
                # Don't raise - computation succeeded even if storage failed
        
        return factor_values

    async def analyze_factor(
        self,
        factor_id: str,
        start_date: date,
        end_date: date,
        n_groups: int = 5,
    ) -> dict[str, Any]:
        """Run IC analysis and layered backtest for a factor.
        
        Args:
            factor_id: Factor ID in database
            start_date: Analysis start date
            end_date: Analysis end date
            n_groups: Number of quantile groups for layered backtest
            
        Returns:
            Dictionary with IC results and layered backtest results
        """
        # Get factor from database
        factor = await self._factor_repo.get_by_id(factor_id)
        if not factor:
            raise FactorComputeError(f"Factor {factor_id} not found")

        logger.info(
            "Analyzing factor %s (%s) from %s to %s",
            factor.factor_name, factor_id, start_date, end_date,
        )

        # Create factor definition from model
        from quant_os_domain_factor.entities.factor import (
            FactorCategory, FactorDirection
        )
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
        factor_values = await self.compute_factor_values(
            factor_def, start_date, end_date,
            factor_id=factor_id, store_to_db=True
        )

        # Fetch market data for forward returns
        ohlcv_data = await self._fetch_ohlcv_data(
            start_date, end_date
        )

        if ohlcv_data.empty:
            raise DataNotFoundError(
                f"No OHLCV data available for {start_date} to {end_date}"
            )

        # Compute forward returns
        forward_returns = self._analyzer.compute_forward_returns(
            ohlcv_data, periods=5
        )

        # Run IC analysis
        ic_result = self._analyzer.compute_ic(
            factor_values, forward_returns
        )

        # Run layered backtest
        layered_result = self._analyzer.layered_backtest(
            factor_values, forward_returns, n_groups=n_groups
        )

        # Save analysis results to database
        analysis_data = {
            "factor_id": factor_id,
            "analysis_date": date.today(),
            "start_date": start_date,
            "end_date": end_date,
            "ic_mean": ic_result.ic_mean,
            "ic_std": ic_result.ic_std,
            "icir": ic_result.icir,
            "rank_ic_mean": ic_result.rank_ic_mean,
            "rank_icir": ic_result.rank_icir,
            "long_short_sharpe": layered_result.long_short_sharpe,
            "layer_results": layered_result.to_dict(),
            "ic_series": ic_result.to_dict(),
        }
        
        await self._factor_repo.save_analysis_result(analysis_data)

        logger.info(
            "Analysis complete for %s: IC=%.4f, ICIR=%.4f, L/S Sharpe=%.4f",
            factor.factor_name, ic_result.ic_mean, ic_result.icir,
            layered_result.long_short_sharpe,
        )

        return {
            "factor_id": factor_id,
            "factor_name": factor.factor_name,
            "ic_analysis": ic_result.to_dict(),
            "layered_backtest": layered_result.to_dict(),
            "analysis_date": str(date.today()),
        }

    async def _fetch_market_data(
        self,
        start_date: date,
        end_date: date,
        stock_pool: list[str] | None = None,
    ) -> pd.DataFrame:
        """Fetch market data needed for factor computation."""
        # This is a simplified implementation
        # In practice, you might need specific data based on factor type
        
        # Fetch OHLCV data
        ohlcv_df = await self._fetch_ohlcv_data(start_date, end_date)
        
        if ohlcv_df.empty:
            return pd.DataFrame()
        
        # Filter by stock pool if specified
        if stock_pool:
            ohlcv_df = ohlcv_df[ohlcv_df["ts_code"].isin(stock_pool)]
        
        return ohlcv_df

    async def _fetch_ohlcv_data(
        self,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch OHLCV data — DB first, auto-sync from provider if empty."""
        from quant_os_infra_market.data_service import DataService

        data_svc = DataService(self._session, self._provider)
        return await data_svc.get_ohlcv_for_factor(start_date, end_date)

    def _calculate_factor_values(
        self,
        factor_def: FactorDefinition,
        market_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate factor values based on factor definition.
        
        Uses the FactorRegistry to compute factor values using registered
        factor calculation functions.
        
        Args:
            factor_def: Factor definition
            market_data: Market data DataFrame
            
        Returns:
            DataFrame with columns [ts_code, trade_date, value, factor_name]
        """
        if market_data.empty:
            return pd.DataFrame(
                columns=["ts_code", "trade_date", "value", "factor_name"]
            )
        
        # Import factor registry
        from quant_os_domain_factor.services.registry import factor_registry
        
        # Check if factor is registered
        if not factor_registry.has(factor_def.factor_name):
            logger.warning(
                "Factor '%s' not found in registry, using fallback calculation",
                factor_def.factor_name,
            )
            return self._calculate_fallback_factor(factor_def, market_data)
        
        try:
            # Compute factor using registry
            factor_values = factor_registry.compute(
                factor_def.factor_name,
                market_data,
                factor_def.params,
            )
            
            # Create result DataFrame
            result = pd.DataFrame({
                "ts_code": market_data["ts_code"],
                "trade_date": market_data["trade_date"],
                "value": factor_values,
                "factor_name": factor_def.factor_name,
            })
            
            # Drop NaN values
            result = result.dropna(subset=["value"])
            
            return result
            
        except Exception as e:
            logger.error(
                "Failed to compute factor '%s': %s",
                factor_def.factor_name, e,
                exc_info=True,
            )
            # Fallback to simple calculation
            return self._calculate_fallback_factor(factor_def, market_data)
    
    def _calculate_fallback_factor(
        self,
        factor_def: FactorDefinition,
        market_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Fallback factor calculation when registry lookup fails.
        
        Uses simple momentum factor as default.
        
        Args:
            factor_def: Factor definition
            market_data: Market data DataFrame
            
        Returns:
            DataFrame with columns [ts_code, trade_date, value, factor_name]
        """
        if market_data.empty:
            return pd.DataFrame(
                columns=["ts_code", "trade_date", "value", "factor_name"]
            )
        
        result_frames = []
        
        for ts_code in market_data["ts_code"].unique():
            stock_data = market_data[market_data["ts_code"] == ts_code].copy()
            
            # Simple momentum factor (close price change)
            if "close" in stock_data.columns:
                stock_data["value"] = stock_data["close"].pct_change(periods=20)
                stock_data["factor_name"] = factor_def.factor_name
                
                result_frames.append(
                    stock_data[["ts_code", "trade_date", "value", "factor_name"]]
                )
        
        if not result_frames:
            return pd.DataFrame(
                columns=["ts_code", "trade_date", "value", "factor_name"]
            )
        
        return pd.concat(result_frames, ignore_index=True).dropna(subset=["value"])
