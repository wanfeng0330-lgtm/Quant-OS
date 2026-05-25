"""Factor computation tools for Agent."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from .base import BaseTool, ToolParameter, ToolParameterType, ToolResult
from .registry import register_tool

logger = logging.getLogger(__name__)


@register_tool
class ComputeFactorTool(BaseTool):
    """Tool to compute factor values."""

    @property
    def name(self) -> str:
        return "compute_factor"

    @property
    def description(self) -> str:
        return "计算因子值，支持Alpha101、技术因子、基本面因子等"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="factor_name",
                type=ToolParameterType.STRING,
                description="因子名称，如 alpha001、momentum、rsi 等",
                required=True,
            ),
            ToolParameter(
                name="start_date",
                type=ToolParameterType.STRING,
                description="开始日期，格式 YYYY-MM-DD",
                required=True,
            ),
            ToolParameter(
                name="end_date",
                type=ToolParameterType.STRING,
                description="结束日期，格式 YYYY-MM-DD",
                required=True,
            ),
            ToolParameter(
                name="stock_pool",
                type=ToolParameterType.ARRAY,
                description="股票池，股票代码列表",
                required=False,
                items={"type": "string"},
            ),
            ToolParameter(
                name="params",
                type=ToolParameterType.OBJECT,
                description="因子参数，如窗口期等",
                required=False,
            ),
        ]

    async def execute(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        stock_pool: list[str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Compute factor values."""
        try:
            from quant_os_app_factor.services.factor_compute_service import FactorComputeService
            from quant_os_infra_market.providers.akshare_provider import AKShareProvider
            from quant_os_infra_market.session import get_session
            from quant_os_domain_factor.entities.factor import FactorDefinition

            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)

            factor_def = FactorDefinition(
                factor_name=factor_name,
                factor_type="custom",
                params=params or {},
            )

            async with get_session() as session:
                provider = AKShareProvider()
                service = FactorComputeService(session, provider)

                result_df = await service.compute_factor_values(
                    factor_def=factor_def,
                    start_date=start,
                    end_date=end,
                    stock_pool=stock_pool,
                )

                if result_df.empty:
                    return ToolResult(
                        success=False,
                        error=f"No factor values computed for {factor_name}",
                    )

                # Convert to serializable format
                values = []
                for _, row in result_df.iterrows():
                    values.append({
                        "ts_code": row["ts_code"],
                        "trade_date": str(row["trade_date"]),
                        "value": float(row["value"]) if pd.notna(row["value"]) else None,
                    })

                return ToolResult(
                    success=True,
                    data={
                        "factor_name": factor_name,
                        "start_date": start_date,
                        "end_date": end_date,
                        "values": values,
                        "count": len(values),
                    },
                )
        except Exception as e:
            logger.error("Failed to compute factor: %s", e)
            return ToolResult(success=False, error=str(e))


@register_tool
class ListFactorsTool(BaseTool):
    """Tool to list available factors."""

    @property
    def name(self) -> str:
        return "list_factors"

    @property
    def description(self) -> str:
        return "列出所有可用的因子，包括Alpha101、技术因子、基本面因子等"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="category",
                type=ToolParameterType.STRING,
                description="因子类别：alpha101、technical、fundamental、custom",
                required=False,
            ),
        ]

    async def execute(self, category: str | None = None) -> ToolResult:
        """List available factors."""
        try:
            from quant_os_infra_factor.registry import factor_registry

            # Get all registered factors
            factors = factor_registry.list_factors()

            # Filter by category if specified
            if category:
                factors = [f for f in factors if f.get("category") == category]

            return ToolResult(
                success=True,
                data={
                    "factors": factors,
                    "count": len(factors),
                },
            )
        except Exception as e:
            logger.error("Failed to list factors: %s", e)
            return ToolResult(success=False, error=str(e))


@register_tool
class AnalyzeFactorTool(BaseTool):
    """Tool to analyze factor performance."""

    @property
    def name(self) -> str:
        return "analyze_factor"

    @property
    def description(self) -> str:
        return "分析因子表现，包括IC、IR、分层收益等"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="factor_name",
                type=ToolParameterType.STRING,
                description="因子名称",
                required=True,
            ),
            ToolParameter(
                name="start_date",
                type=ToolParameterType.STRING,
                description="开始日期，格式 YYYY-MM-DD",
                required=True,
            ),
            ToolParameter(
                name="end_date",
                type=ToolParameterType.STRING,
                description="结束日期，格式 YYYY-MM-DD",
                required=True,
            ),
            ToolParameter(
                name="method",
                type=ToolParameterType.STRING,
                description="分析方法：ic、layered、both",
                required=False,
                default="both",
            ),
        ]

    async def execute(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        method: str = "both",
    ) -> ToolResult:
        """Analyze factor performance."""
        try:
            from quant_os_domain_factor.services.analyzer import FactorAnalyzer
            from quant_os_app_factor.services.factor_compute_service import FactorComputeService
            from quant_os_infra_market.providers.akshare_provider import AKShareProvider
            from quant_os_infra_market.session import get_session
            from quant_os_domain_factor.entities.factor import FactorDefinition

            # Parse dates
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)

            async with get_session() as session:
                provider = AKShareProvider()
                service = FactorComputeService(session, provider)

                # First compute factor values
                factor_def = FactorDefinition(
                    factor_name=factor_name,
                    factor_type="custom",
                )

                factor_df = await service.compute_factor_values(
                    factor_def=factor_def,
                    start_date=start,
                    end_date=end,
                )

                if factor_df.empty:
                    return ToolResult(
                        success=False,
                        error=f"No factor values for {factor_name}",
                    )

                # Analyze factor
                analyzer = FactorAnalyzer()
                results = {}

                if method in ("ic", "both"):
                    ic_result = analyzer.compute_ic(factor_df)
                    results["ic"] = {
                        "mean_ic": ic_result.mean_ic,
                        "ic_ir": ic_result.ic_ir,
                        "ic_positive_ratio": ic_result.ic_positive_ratio,
                    }

                if method in ("layered", "both"):
                    layered_result = analyzer.compute_layered_returns(factor_df)
                    results["layered"] = {
                        "layers": [
                            {
                                "layer": l.layer,
                                "return": l.mean_return,
                                "sharpe": l.sharpe_ratio,
                            }
                            for l in layered_result
                        ]
                    }

                return ToolResult(
                    success=True,
                    data={
                        "factor_name": factor_name,
                        "period": f"{start_date} to {end_date}",
                        "analysis": results,
                    },
                )
        except Exception as e:
            logger.error("Failed to analyze factor: %s", e)
            return ToolResult(success=False, error=str(e))