"""Trading calendar repository implementation."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_infra_market.models.calendar_model import TradingCalendarModel

logger = logging.getLogger(__name__)


class TradingCalendarRepository:
    """Repository for trading calendar operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_trading_days(
        self,
        start_date: date,
        end_date: date,
        exchange: str = "ALL",
    ) -> list[TradingCalendarModel]:
        result = await self._session.execute(
            select(TradingCalendarModel)
            .where(TradingCalendarModel.cal_date >= start_date)
            .where(TradingCalendarModel.cal_date <= end_date)
            .where(TradingCalendarModel.is_open == True)
            .order_by(TradingCalendarModel.cal_date)
        )
        return list(result.scalars().all())

    async def is_trading_day(self, d: date) -> bool:
        result = await self._session.execute(
            select(TradingCalendarModel)
            .where(TradingCalendarModel.cal_date == d)
        )
        cal = result.scalar_one_or_none()
        return cal.is_open if cal else d.weekday() < 5

    async def get_previous_trading_day(self, d: date) -> date | None:
        result = await self._session.execute(
            select(TradingCalendarModel)
            .where(TradingCalendarModel.cal_date < d)
            .where(TradingCalendarModel.is_open == True)
            .order_by(TradingCalendarModel.cal_date.desc())
            .limit(1)
        )
        cal = result.scalar_one_or_none()
        return cal.cal_date if cal else None

    async def bulk_upsert(self, calendar_data: list[dict]) -> int:
        upserted = 0
        for data in calendar_data:
            existing = await self._session.execute(
                select(TradingCalendarModel)
                .where(TradingCalendarModel.cal_date == data["cal_date"])
            )
            cal = existing.scalar_one_or_none()
            if cal:
                cal.is_open = data["is_open"]
                cal.exchange = data.get("exchange", "ALL")
                cal.pre_trade_date = data.get("pre_trade_date")
            else:
                self._session.add(TradingCalendarModel(**data))
            upserted += 1

        await self._session.flush()
        logger.info("Upserted %d calendar entries", upserted)
        return upserted
