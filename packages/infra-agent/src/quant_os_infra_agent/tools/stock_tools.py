"""Stock query tools for Agent."""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseTool, ToolParameter, ToolParameterType, ToolResult
from .registry import register_tool

logger = logging.getLogger(__name__)


@register_tool
class GetStockInfoTool(BaseTool):
    """Tool to get stock information by stock code."""

    @property
    def name(self) -> str:
        return "get_stock_info"

    @property
    def description(self) -> str:
        return "获取股票基本信息，包括股票代码、名称、交易所、行业等"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="ts_code",
                type=ToolParameterType.STRING,
                description="股票代码，如 000001.SZ",
                required=True,
            ),
        ]

    async def execute(self, ts_code: str) -> ToolResult:
        """Get stock information by ts_code."""
        try:
            from quant_os_infra_market.session import get_session
            from quant_os_infra_market.data_service import DataService
            from quant_os_infra_market.providers.akshare_provider import AKShareProvider

            async with get_session() as session:
                svc = DataService(session, AKShareProvider())
                stock = await svc.get_stock(ts_code)

                if not stock:
                    return ToolResult(
                        success=False,
                        error=f"Stock {ts_code} not found",
                    )

                return ToolResult(success=True, data=stock)
        except Exception as e:
            logger.error("Failed to get stock info: %s", e)
            return ToolResult(success=False, error=str(e))


@register_tool
class SearchStocksTool(BaseTool):
    """Tool to search stocks by keyword."""

    @property
    def name(self) -> str:
        return "search_stocks"

    @property
    def description(self) -> str:
        return "搜索股票，支持按代码、名称、拼音等关键词搜索"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="keyword",
                type=ToolParameterType.STRING,
                description="搜索关键词，可以是股票代码、名称或拼音",
                required=True,
            ),
            ToolParameter(
                name="limit",
                type=ToolParameterType.INTEGER,
                description="返回结果数量限制",
                required=False,
                default=20,
            ),
        ]

    async def execute(self, keyword: str, limit: int = 20) -> ToolResult:
        """Search stocks by keyword."""
        try:
            from quant_os_infra_market.session import get_session
            from quant_os_infra_market.data_service import DataService
            from quant_os_infra_market.providers.akshare_provider import AKShareProvider

            async with get_session() as session:
                svc = DataService(session, AKShareProvider())
                stocks = await svc.search_stocks(keyword, limit)

                return ToolResult(
                    success=True,
                    data={"stocks": stocks, "count": len(stocks)},
                )
        except Exception as e:
            logger.error("Failed to search stocks: %s", e)
            return ToolResult(success=False, error=str(e))


@register_tool
class ListStocksTool(BaseTool):
    """Tool to list stocks with filters."""

    @property
    def name(self) -> str:
        return "list_stocks"

    @property
    def description(self) -> str:
        return "列出股票列表，支持按交易所、板块等条件筛选"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="exchange",
                type=ToolParameterType.STRING,
                description="交易所代码，如 SZ（深圳）、SH（上海）",
                required=False,
            ),
            ToolParameter(
                name="board",
                type=ToolParameterType.STRING,
                description="板块，如 主板、创业板、科创板",
                required=False,
            ),
            ToolParameter(
                name="is_st",
                type=ToolParameterType.BOOLEAN,
                description="是否ST股票",
                required=False,
            ),
            ToolParameter(
                name="status",
                type=ToolParameterType.STRING,
                description="股票状态，如 L（上市）、D（退市）",
                required=False,
            ),
            ToolParameter(
                name="page",
                type=ToolParameterType.INTEGER,
                description="页码",
                required=False,
                default=1,
            ),
            ToolParameter(
                name="size",
                type=ToolParameterType.INTEGER,
                description="每页数量",
                required=False,
                default=50,
            ),
        ]

    async def execute(
        self,
        exchange: str | None = None,
        board: str | None = None,
        is_st: bool | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> ToolResult:
        """List stocks with filters."""
        try:
            from quant_os_infra_market.session import get_session
            from quant_os_infra_market.data_service import DataService
            from quant_os_infra_market.providers.akshare_provider import AKShareProvider

            async with get_session() as session:
                svc = DataService(session, AKShareProvider())
                result = await svc.list_stocks(
                    exchange=exchange, board=board, is_st=is_st, status=status,
                    page=page, size=size,
                )

                return ToolResult(
                    success=True,
                    data={
                        "stocks": result["items"],
                        "total": result["total"],
                        "page": result["page"],
                        "size": result["size"],
                    },
                )
        except Exception as e:
            logger.error("Failed to list stocks: %s", e)
            return ToolResult(success=False, error=str(e))


@register_tool
class GetStockPriceTool(BaseTool):
    """Tool to get stock price data."""

    @property
    def name(self) -> str:
        return "get_stock_price"

    @property
    def description(self) -> str:
        return "获取股票价格数据，包括最新价、涨跌幅等"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="ts_code",
                type=ToolParameterType.STRING,
                description="股票代码，如 000001.SZ",
                required=True,
            ),
            ToolParameter(
                name="start_date",
                type=ToolParameterType.STRING,
                description="开始日期，格式 YYYYMMDD",
                required=False,
            ),
            ToolParameter(
                name="end_date",
                type=ToolParameterType.STRING,
                description="结束日期，格式 YYYYMMDD",
                required=False,
            ),
            ToolParameter(
                name="limit",
                type=ToolParameterType.INTEGER,
                description="返回数据条数",
                required=False,
                default=30,
            ),
        ]

    async def execute(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 30,
    ) -> ToolResult:
        """Get stock price data — DB first, auto-syncs from AKShare if empty."""
        try:
            from datetime import date as date_type
            from quant_os_infra_market.session import get_session
            from quant_os_infra_market.data_service import DataService
            from quant_os_infra_market.providers.akshare_provider import AKShareProvider

            sd = date_type.fromisoformat(start_date) if start_date else None
            ed = date_type.fromisoformat(end_date) if end_date else None

            async with get_session() as session:
                svc = DataService(session, AKShareProvider())
                df = await svc.get_ohlcv(ts_code, sd, ed)

                if df.empty:
                    return ToolResult(
                        success=False,
                        error=f"No price data found for {ts_code}",
                    )

                df = df.tail(limit)
                prices = []
                for _, row in df.iterrows():
                    prices.append({
                        "trade_date": str(row["trade_date"]),
                        "open": float(row["open"]) if row.get("open") else None,
                        "high": float(row["high"]) if row.get("high") else None,
                        "low": float(row["low"]) if row.get("low") else None,
                        "close": float(row["close"]) if row.get("close") else None,
                        "volume": float(row["volume"]) if row.get("volume") else None,
                        "amount": float(row["amount"]) if row.get("amount") else None,
                        "pct_chg": float(row["pct_chg"]) if row.get("pct_chg") else None,
                    })

                return ToolResult(
                    success=True,
                    data={"ts_code": ts_code, "prices": prices, "count": len(prices)},
                )
        except Exception as e:
            logger.error("Failed to get stock price: %s", e)
            return ToolResult(success=False, error=str(e))