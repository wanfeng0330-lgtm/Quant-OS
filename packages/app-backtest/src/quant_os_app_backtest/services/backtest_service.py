"""Backtest service - orchestrates backtest execution and result management."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_infra_strategy.engines.vectorized_engine import (
    VectorizedBacktestEngine,
    BacktestConfig,
    BacktestResult,
)
from quant_os_infra_strategy.models.strategy_model import StrategyModel, BacktestRunModel
from quant_os_infra_market.providers.base import DataProvider
from quant_os_shared.errors import BacktestError, BacktestExecutionError, BacktestConfigError

logger = logging.getLogger(__name__)


def build_factor_rank_signals(
    factor_values: pd.DataFrame,
    direction: Any,
    top_n: int,
) -> pd.DataFrame:
    """Build equal-weight buy signals from factor rankings."""
    if factor_values.empty:
        return pd.DataFrame(columns=["ts_code", "trade_date", "signal", "weight"])

    direction_value = getattr(direction, "value", direction)
    ascending = direction_value == -1
    signals: list[dict[str, Any]] = []

    for current_date in sorted(factor_values["trade_date"].unique()):
        day_factors = factor_values[factor_values["trade_date"] == current_date].dropna(subset=["value"])
        if day_factors.empty:
            continue

        selected = day_factors.sort_values("value", ascending=ascending).head(top_n)
        weight = 1.0 / len(selected) if len(selected) else 0.0
        for _, row in selected.iterrows():
            signals.append(
                {
                    "ts_code": row["ts_code"],
                    "trade_date": current_date,
                    "signal": 1,
                    "weight": weight,
                }
            )

    if not signals:
        return pd.DataFrame(columns=["ts_code", "trade_date", "signal", "weight"])
    return pd.DataFrame(signals)


class BacktestService:
    """Orchestrates backtest execution and result management."""

    def __init__(
        self,
        session: AsyncSession,
        provider: DataProvider,
    ) -> None:
        self._session = session
        self._provider = provider

    async def create_backtest_run(
        self,
        strategy_id: str,
        start_date: date,
        end_date: date,
        benchmark_code: str = "000300.SH",
        engine: str = "internal",
        initial_capital: Decimal = Decimal("1000000"),
        commission_rate: Decimal = Decimal("0.0003"),
        slippage_rate: Decimal = Decimal("0.001"),
    ) -> BacktestRunModel:
        """Create a new backtest run.
        
        Args:
            strategy_id: Strategy ID to backtest
            start_date: Backtest start date
            end_date: Backtest end date
            benchmark_code: Benchmark index code
            engine: Backtest engine to use
            initial_capital: Initial capital amount
            commission_rate: Commission rate
            slippage_rate: Slippage rate
            
        Returns:
            Created BacktestRunModel
        """
        # Validate strategy exists
        from sqlalchemy import select
        result = await self._session.execute(
            select(StrategyModel).where(StrategyModel.id == strategy_id)
        )
        strategy = result.scalar_one_or_none()
        
        if not strategy:
            raise BacktestError(f"Strategy {strategy_id} not found")
        
        # Create backtest run
        backtest_run = BacktestRunModel(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            benchmark_code=benchmark_code,
            engine=engine,
            status="pending",
            config_snapshot={
                "initial_capital": str(initial_capital),
                "commission_rate": str(commission_rate),
                "slippage_rate": str(slippage_rate),
            },
        )
        
        self._session.add(backtest_run)
        await self._session.flush()
        
        logger.info(
            "Created backtest run %s for strategy %s (%s to %s)",
            backtest_run.id, strategy_id, start_date, end_date,
        )
        
        return backtest_run

    async def execute_backtest(
        self,
        backtest_run_id: str,
    ) -> BacktestResult:
        """Execute a backtest run.
        
        Args:
            backtest_run_id: Backtest run ID to execute
            
        Returns:
            BacktestResult with performance metrics
        """
        # Get backtest run
        from sqlalchemy import select
        result = await self._session.execute(
            select(BacktestRunModel).where(BacktestRunModel.id == backtest_run_id)
        )
        backtest_run = result.scalar_one_or_none()
        
        if not backtest_run:
            raise BacktestError(f"Backtest run {backtest_run_id} not found")
        
        if backtest_run.status not in ["pending", "failed"]:
            raise BacktestError(
                f"Backtest run {backtest_run_id} cannot be executed (status: {backtest_run.status})"
            )
        
        # Update status to running
        backtest_run.status = "running"
        backtest_run.started_at = datetime.now()
        await self._session.flush()
        
        try:
            # Get strategy
            strategy_result = await self._session.execute(
                select(StrategyModel).where(StrategyModel.id == backtest_run.strategy_id)
            )
            strategy = strategy_result.scalar_one_or_none()
            
            if not strategy:
                raise BacktestError(f"Strategy {backtest_run.strategy_id} not found")
            
            # Get market data
            market_data = await self._fetch_market_data(
                backtest_run.start_date,
                backtest_run.end_date,
            )
            
            if market_data.empty:
                raise BacktestExecutionError(
                    "No market data available for backtest period"
                )
            
            # Get benchmark data
            benchmark_data = await self._fetch_benchmark_data(
                backtest_run.benchmark_code,
                backtest_run.start_date,
                backtest_run.end_date,
            )
            
            # Generate trading signals based on strategy
            signals = await self._generate_signals(
                strategy, market_data, backtest_run.start_date, backtest_run.end_date
            )
            
            # Create backtest config
            config = BacktestConfig(
                initial_capital=Decimal(backtest_run.config_snapshot.get("initial_capital", "1000000")),
                commission_rate=Decimal(backtest_run.config_snapshot.get("commission_rate", "0.0003")),
                slippage_rate=Decimal(backtest_run.config_snapshot.get("slippage_rate", "0.001")),
                benchmark_code=backtest_run.benchmark_code,
            )
            
            # Create and run engine
            engine = VectorizedBacktestEngine(config)
            backtest_result = engine.run(signals, market_data, benchmark_data)
            
            # Update backtest run with results
            await self._update_backtest_run_with_results(
                backtest_run, backtest_result
            )
            
            # Commit changes
            await self._session.commit()
            
            logger.info(
                "Backtest %s completed: total_return=%.2f%%, sharpe=%.2f",
                backtest_run_id,
                backtest_result.total_return * 100,
                backtest_result.sharpe_ratio,
            )
            
            return backtest_result
            
        except Exception as e:
            # Update status to failed
            backtest_run.status = "failed"
            backtest_run.error_message = str(e)
            backtest_run.completed_at = datetime.now()
            await self._session.commit()
            
            logger.error(
                "Backtest %s failed: %s",
                backtest_run_id, e, exc_info=True,
            )
            raise

    async def get_backtest_run(self, backtest_run_id: str) -> BacktestRunModel | None:
        """Get backtest run by ID."""
        from sqlalchemy import select
        result = await self._session.execute(
            select(BacktestRunModel).where(BacktestRunModel.id == backtest_run_id)
        )
        return result.scalar_one_or_none()

    async def list_backtest_runs(
        self,
        strategy_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[BacktestRunModel]:
        """List backtest runs with optional filters."""
        from sqlalchemy import select
        
        query = select(BacktestRunModel).order_by(BacktestRunModel.created_at.desc())
        
        if strategy_id:
            query = query.where(BacktestRunModel.strategy_id == strategy_id)
        if status:
            query = query.where(BacktestRunModel.status == status)
        
        query = query.limit(limit)
        
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def cancel_backtest_run(self, backtest_run_id: str) -> bool:
        """Cancel a pending or running backtest."""
        backtest_run = await self.get_backtest_run(backtest_run_id)
        
        if not backtest_run:
            return False
        
        if backtest_run.status not in ["pending", "running"]:
            return False
        
        backtest_run.status = "cancelled"
        backtest_run.error_message = "Cancelled by user"
        backtest_run.completed_at = datetime.now()
        
        await self._session.commit()
        
        logger.info("Cancelled backtest run %s", backtest_run_id)
        return True

    async def _fetch_market_data(
        self,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch market data — DB first, auto-sync from provider if empty."""
        from quant_os_infra_market.data_service import DataService

        data_svc = DataService(self._session, self._provider)
        return await data_svc.get_ohlcv_for_factor(start_date, end_date)

    async def _fetch_benchmark_data(
        self,
        benchmark_code: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame | None:
        """Fetch benchmark index data — DB first, auto-sync if empty."""
        from quant_os_infra_market.data_service import DataService

        data_svc = DataService(self._session, self._provider)
        df = await data_svc.get_ohlcv(benchmark_code, start_date, end_date)
        return df if not df.empty else None

    async def _generate_signals(
        self,
        strategy: StrategyModel,
        market_data: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Generate trading signals based on strategy configuration.
        
        Supports two modes:
        1. Simple mode: Equal-weight buy-and-hold
        2. Factor mode: Use factor values to generate signals
        
        Strategy config should contain:
        - mode: "simple" or "factor" (default: "simple")
        - factor_id: Factor ID for factor mode
        - top_n: Number of top stocks to select (default: max_holdings)
        """
        # Get strategy configuration
        config = strategy.config or {}
        mode = config.get("mode", "simple")
        
        if mode == "factor":
            return await self._generate_factor_signals(
                strategy, market_data, start_date, end_date, config
            )
        else:
            return self._generate_simple_signals(strategy, market_data)
    
    def _generate_simple_signals(
        self,
        strategy: StrategyModel,
        market_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Generate simple equal-weight buy-and-hold signals."""
        # Get unique stocks and dates from market data
        stocks = market_data["ts_code"].unique()
        dates = sorted(market_data["trade_date"].unique())
        
        if len(stocks) == 0 or len(dates) == 0:
            return pd.DataFrame(columns=["ts_code", "trade_date", "signal", "weight"])
        
        # Generate simple equal-weight buy-and-hold signals for demonstration
        signals = []
        
        # Select top N stocks (simplified)
        max_holdings = strategy.max_holdings or 10
        selected_stocks = stocks[:min(max_holdings, len(stocks))]
        
        for current_date in dates:
            for ts_code in selected_stocks:
                signals.append({
                    "ts_code": ts_code,
                    "trade_date": current_date,
                    "signal": 1,  # Buy signal
                    "weight": 1.0 / len(selected_stocks),  # Equal weight
                })
        
        return pd.DataFrame(signals)
    
    async def _generate_factor_signals(
        self,
        strategy: StrategyModel,
        market_data: pd.DataFrame,
        start_date: date,
        end_date: date,
        config: dict,
    ) -> pd.DataFrame:
        """Generate signals based on factor values.
        
        This method uses the factor engine to compute factor values
        and generate trading signals based on factor rankings.
        """
        factor_id = config.get("factor_id")
        if not factor_id:
            logger.warning("No factor_id specified in strategy config, falling back to simple mode")
            return self._generate_simple_signals(strategy, market_data)
        
        # Import factor service
        from quant_os_app_factor.services.factor_compute_service import FactorComputeService
        from quant_os_infra_factor.repositories.factor_repo import FactorRepository
        
        # Get factor definition from database
        factor_repo = FactorRepository(self._session)
        factor = await factor_repo.get_by_id(factor_id)
        
        if not factor:
            logger.warning("Factor %s not found, falling back to simple mode", factor_id)
            return self._generate_simple_signals(strategy, market_data)
        
        # Create factor definition
        from quant_os_domain_factor.entities.factor import (
            FactorDefinition, FactorCategory, FactorDirection
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
        factor_service = FactorComputeService(
            session=self._session,
            provider=self._provider,
        )
        
        factor_values = await factor_service.compute_factor_values(
            factor_def=factor_def,
            start_date=start_date,
            end_date=end_date,
        )
        
        if factor_values.empty:
            logger.warning("No factor values computed, falling back to simple mode")
            return self._generate_simple_signals(strategy, market_data)
        
        top_n = config.get("top_n", strategy.max_holdings or 10)

        signals = build_factor_rank_signals(factor_values, factor_def.direction, top_n)
        if signals.empty:
            logger.warning("No signals generated from factor, falling back to simple mode")
            return self._generate_simple_signals(strategy, market_data)

        return signals

    async def _update_backtest_run_with_results(
        self,
        backtest_run: BacktestRunModel,
        result: BacktestResult,
    ) -> None:
        """Update backtest run with execution results."""
        backtest_run.status = "completed"
        backtest_run.completed_at = datetime.now()
        
        # Update performance metrics
        backtest_run.annual_return = result.annual_return
        backtest_run.sharpe_ratio = result.sharpe_ratio
        backtest_run.max_drawdown = result.max_drawdown
        backtest_run.calmar_ratio = result.calmar_ratio
        backtest_run.win_rate = result.win_rate
        backtest_run.profit_loss_ratio = result.profit_loss_ratio
        backtest_run.avg_turnover = result.avg_turnover
        backtest_run.alpha = result.alpha
        backtest_run.beta = result.beta
        backtest_run.information_ratio = result.information_ratio
        backtest_run.total_return = result.total_return
        backtest_run.benchmark_return = result.benchmark_return
        backtest_run.excess_return = result.excess_return
        
        # Update time series data
        backtest_run.nav_series = result.nav_series
        backtest_run.drawdown_series = result.drawdown_series
        backtest_run.monthly_returns = result.monthly_returns
        backtest_run.position_history = result.position_history
        backtest_run.trade_log = result.trade_log
        
        await self._session.flush()
