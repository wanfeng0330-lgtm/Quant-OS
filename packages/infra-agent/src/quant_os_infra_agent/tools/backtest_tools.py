"""Backtest execution tools for Agent."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from .base import BaseTool, ToolParameter, ToolParameterType, ToolResult
from .registry import register_tool

logger = logging.getLogger(__name__)


@register_tool
class RunBacktestTool(BaseTool):
    """Tool to run a backtest."""

    @property
    def name(self) -> str:
        return "run_backtest"

    @property
    def description(self) -> str:
        return "执行策略回测，计算策略的收益、风险等指标"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="strategy_id",
                type=ToolParameterType.STRING,
                description="策略ID",
                required=True,
            ),
            ToolParameter(
                name="start_date",
                type=ToolParameterType.STRING,
                description="回测开始日期，格式 YYYY-MM-DD",
                required=True,
            ),
            ToolParameter(
                name="end_date",
                type=ToolParameterType.STRING,
                description="回测结束日期，格式 YYYY-MM-DD",
                required=True,
            ),
            ToolParameter(
                name="benchmark",
                type=ToolParameterType.STRING,
                description="基准指数代码，默认 000300.SH（沪深300）",
                required=False,
                default="000300.SH",
            ),
            ToolParameter(
                name="initial_capital",
                type=ToolParameterType.NUMBER,
                description="初始资金，默认 1000000",
                required=False,
                default=1000000,
            ),
            ToolParameter(
                name="commission_rate",
                type=ToolParameterType.NUMBER,
                description="手续费率，默认 0.0003",
                required=False,
                default=0.0003,
            ),
            ToolParameter(
                name="slippage_rate",
                type=ToolParameterType.NUMBER,
                description="滑点率，默认 0.001",
                required=False,
                default=0.001,
            ),
        ]

    async def execute(
        self,
        strategy_id: str,
        start_date: str,
        end_date: str,
        benchmark: str = "000300.SH",
        initial_capital: float = 1000000,
        commission_rate: float = 0.0003,
        slippage_rate: float = 0.001,
    ) -> ToolResult:
        """Run a backtest."""
        try:
            from quant_os_app_backtest.services.backtest_service import BacktestService
            from quant_os_infra_market.providers.akshare_provider import AKShareProvider
            from quant_os_infra_market.session import get_session

            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)

            async with get_session() as session:
                provider = AKShareProvider()
                service = BacktestService(session, provider)

                backtest_run = await service.create_backtest_run(
                    strategy_id=strategy_id,
                    start_date=start,
                    end_date=end,
                    benchmark_code=benchmark,
                    initial_capital=Decimal(str(initial_capital)),
                    commission_rate=Decimal(str(commission_rate)),
                    slippage_rate=Decimal(str(slippage_rate)),
                )

                result = await service.execute_backtest(backtest_run.id)

                return ToolResult(
                    success=True,
                    data={
                        "backtest_id": backtest_run.id,
                        "strategy_id": strategy_id,
                        "period": f"{start_date} to {end_date}",
                        "results": {
                            "total_return": float(result.total_return),
                            "annual_return": float(result.annual_return),
                            "max_drawdown": float(result.max_drawdown),
                            "sharpe_ratio": float(result.sharpe_ratio),
                            "win_rate": float(result.win_rate) if result.win_rate else None,
                            "profit_loss_ratio": float(result.profit_loss_ratio) if result.profit_loss_ratio else None,
                            "trade_count": result.trade_count,
                        },
                        "benchmark_return": float(result.benchmark_return) if result.benchmark_return else None,
                        "excess_return": float(result.excess_return) if result.excess_return else None,
                    },
                )
        except Exception as e:
            logger.error("Failed to run backtest: %s", e)
            return ToolResult(success=False, error=str(e))


@register_tool
class GetBacktestResultTool(BaseTool):
    """Tool to get backtest result."""

    @property
    def name(self) -> str:
        return "get_backtest_result"

    @property
    def description(self) -> str:
        return "获取已执行回测的结果"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="backtest_id",
                type=ToolParameterType.STRING,
                description="回测ID",
                required=True,
            ),
        ]

    async def execute(self, backtest_id: str) -> ToolResult:
        """Get backtest result."""
        try:
            from quant_os_infra_strategy.models.strategy_model import BacktestRunModel
            from quant_os_infra_market.session import get_session
            from sqlalchemy import select

            async with get_session() as session:
                result = await session.execute(
                    select(BacktestRunModel).where(BacktestRunModel.id == backtest_id)
                )
                backtest_run = result.scalar_one_or_none()

                if not backtest_run:
                    return ToolResult(
                        success=False,
                        error=f"Backtest {backtest_id} not found",
                    )

                # Get results from the run
                results_data = backtest_run.results or {}

                return ToolResult(
                    success=True,
                    data={
                        "backtest_id": backtest_id,
                        "strategy_id": backtest_run.strategy_id,
                        "status": backtest_run.status,
                        "start_date": str(backtest_run.start_date),
                        "end_date": str(backtest_run.end_date),
                        "benchmark": backtest_run.benchmark_code,
                        "results": results_data,
                        "created_at": backtest_run.created_at.isoformat() if backtest_run.created_at else None,
                        "completed_at": backtest_run.completed_at.isoformat() if backtest_run.completed_at else None,
                    },
                )
        except Exception as e:
            logger.error("Failed to get backtest result: %s", e)
            return ToolResult(success=False, error=str(e))


@register_tool
class ListBacktestsTool(BaseTool):
    """Tool to list backtest runs."""

    @property
    def name(self) -> str:
        return "list_backtests"

    @property
    def description(self) -> str:
        return "列出回测历史记录"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="strategy_id",
                type=ToolParameterType.STRING,
                description="策略ID，筛选特定策略的回测",
                required=False,
            ),
            ToolParameter(
                name="status",
                type=ToolParameterType.STRING,
                description="回测状态：pending、running、completed、failed",
                required=False,
            ),
            ToolParameter(
                name="limit",
                type=ToolParameterType.INTEGER,
                description="返回数量限制",
                required=False,
                default=20,
            ),
        ]

    async def execute(
        self,
        strategy_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> ToolResult:
        """List backtest runs."""
        try:
            from quant_os_infra_strategy.models.strategy_model import BacktestRunModel
            from quant_os_infra_market.session import get_session
            from sqlalchemy import select, desc

            async with get_session() as session:
                query = select(BacktestRunModel)

                if strategy_id:
                    query = query.where(BacktestRunModel.strategy_id == strategy_id)
                if status:
                    query = query.where(BacktestRunModel.status == status)

                query = query.order_by(desc(BacktestRunModel.created_at)).limit(limit)

                result = await session.execute(query)
                backtests = result.scalars().all()

                return ToolResult(
                    success=True,
                    data={
                        "backtests": [
                            {
                                "id": b.id,
                                "strategy_id": b.strategy_id,
                                "status": b.status,
                                "start_date": str(b.start_date),
                                "end_date": str(b.end_date),
                                "benchmark": b.benchmark_code,
                                "created_at": b.created_at.isoformat() if b.created_at else None,
                            }
                            for b in backtests
                        ],
                        "count": len(backtests),
                    },
                )
        except Exception as e:
            logger.error("Failed to list backtests: %s", e)
            return ToolResult(success=False, error=str(e))