"""Stock query service."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_infra_market.repositories.stock_repo import StockRepository
from quant_os_infra_market.cache.market_cache import MarketCache

logger = logging.getLogger(__name__)


class StockQueryService:
    """Service for querying stock data with caching support."""

    def __init__(
        self,
        session: AsyncSession,
        cache: MarketCache | None = None,
    ) -> None:
        self._session = session
        self._cache = cache
        self._repo = StockRepository(session)

    async def get_stock(self, ts_code: str) -> dict[str, Any] | None:
        stock = await self._repo.get_by_ts_code(ts_code)
        if not stock:
            return None
        return self._stock_to_dict(stock)

    async def list_stocks(
        self,
        exchange: str | None = None,
        board: str | None = None,
        is_st: bool | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> dict[str, Any]:
        if self._cache and not any([exchange, board, is_st is not None, status]):
            cached = await self._cache.get_stock_list()
            if cached:
                start = (page - 1) * size
                end = start + size
                return {
                    "items": cached[start:end],
                    "total": len(cached),
                    "page": page,
                    "size": size,
                }

        stocks, total = await self._repo.list_stocks(
            exchange=exchange,
            board=board,
            is_st=is_st,
            status=status,
            offset=(page - 1) * size,
            limit=size,
        )

        return {
            "items": [self._stock_to_dict(s) for s in stocks],
            "total": total,
            "page": page,
            "size": size,
        }

    async def search_stocks(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        from sqlalchemy import select, or_
        from quant_os_infra_market.models.stock_model import StockModel

        result = await self._session.execute(
            select(StockModel)
            .where(
                or_(
                    StockModel.ts_code.ilike(f"%{keyword}%"),
                    StockModel.symbol.ilike(f"%{keyword}%"),
                    StockModel.name.ilike(f"%{keyword}%"),
                )
            )
            .limit(limit)
        )
        stocks = result.scalars().all()
        return [self._stock_to_dict(s) for s in stocks]

    @staticmethod
    def _stock_to_dict(stock) -> dict[str, Any]:
        return {
            "ts_code": stock.ts_code,
            "symbol": stock.symbol,
            "name": stock.name,
            "exchange": stock.exchange,
            "board": stock.board,
            "industry": stock.industry,
            "is_st": stock.is_st,
            "is_hs": stock.is_hs,
            "list_date": str(stock.list_date) if stock.list_date else None,
            "total_share": float(stock.total_share) if stock.total_share else None,
            "float_share": float(stock.float_share) if stock.float_share else None,
            "status": stock.status,
        }
