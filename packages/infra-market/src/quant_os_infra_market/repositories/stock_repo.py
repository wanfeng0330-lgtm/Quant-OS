"""Stock repository implementation."""

from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_infra_market.models.stock_model import StockModel

logger = logging.getLogger(__name__)


class StockRepository:
    """Repository for stock CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ts_code(self, ts_code: str) -> StockModel | None:
        result = await self._session.execute(
            select(StockModel).where(StockModel.ts_code == ts_code)
        )
        return result.scalar_one_or_none()

    async def list_stocks(
        self,
        exchange: str | None = None,
        board: str | None = None,
        is_st: bool | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[StockModel], int]:
        query = select(StockModel)
        count_query = select(func.count()).select_from(StockModel)

        if exchange:
            query = query.where(StockModel.exchange == exchange)
            count_query = count_query.where(StockModel.exchange == exchange)
        if board:
            query = query.where(StockModel.board == board)
            count_query = count_query.where(StockModel.board == board)
        if is_st is not None:
            query = query.where(StockModel.is_st == is_st)
            count_query = count_query.where(StockModel.is_st == is_st)
        if status:
            query = query.where(StockModel.status == status)
            count_query = count_query.where(StockModel.status == status)

        total_result = await self._session.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(StockModel.ts_code).offset(offset).limit(limit)
        result = await self._session.execute(query)
        stocks = list(result.scalars().all())

        return stocks, total

    async def upsert_stock(self, stock_data: dict) -> StockModel:
        ts_code = stock_data["ts_code"]
        existing = await self.get_by_ts_code(ts_code)

        if existing:
            for key, value in stock_data.items():
                if key != "ts_code" and value is not None:
                    setattr(existing, key, value)
            await self._session.flush()
            return existing
        else:
            stock = StockModel(**stock_data)
            self._session.add(stock)
            await self._session.flush()
            return stock

    async def bulk_upsert(self, stocks_data: list[dict]) -> int:
        upserted = 0
        for stock_data in stocks_data:
            await self.upsert_stock(stock_data)
            upserted += 1
        return upserted

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(StockModel))
        return result.scalar() or 0
