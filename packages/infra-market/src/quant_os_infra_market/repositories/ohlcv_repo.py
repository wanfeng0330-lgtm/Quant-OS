"""OHLCV repository implementation."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

logger = logging.getLogger(__name__)


class OHLCVRepository:
    """Repository for OHLCV data operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_daily(
        self,
        ts_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 1000,
    ) -> list[OHLCVDailyModel]:
        query = select(OHLCVDailyModel).where(OHLCVDailyModel.ts_code == ts_code)
        if start_date:
            query = query.where(OHLCVDailyModel.trade_date >= start_date)
        if end_date:
            query = query.where(OHLCVDailyModel.trade_date <= end_date)
        query = query.order_by(OHLCVDailyModel.trade_date.desc()).limit(limit)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_daily_cross_section(
        self,
        trade_date: date,
        ts_codes: list[str] | None = None,
    ) -> list[OHLCVDailyModel]:
        query = select(OHLCVDailyModel).where(OHLCVDailyModel.trade_date == trade_date)
        if ts_codes:
            query = query.where(OHLCVDailyModel.ts_code.in_(ts_codes))

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_latest_date(self, ts_code: str) -> date | None:
        result = await self._session.execute(
            select(func.max(OHLCVDailyModel.trade_date))
            .where(OHLCVDailyModel.ts_code == ts_code)
        )
        return result.scalar_one_or_none()

    async def bulk_insert(self, records: list[dict]) -> int:
        if not records:
            return 0

        inserted = 0
        for record in records:
            existing = await self._session.execute(
                select(OHLCVDailyModel)
                .where(OHLCVDailyModel.ts_code == record["ts_code"])
                .where(OHLCVDailyModel.trade_date == record["trade_date"])
            )
            if not existing.scalar_one_or_none():
                self._session.add(OHLCVDailyModel(**record))
                inserted += 1

        await self._session.flush()
        logger.info("Bulk inserted %d new OHLCV daily records", inserted)
        return inserted

    async def get_as_dataframe(
        self,
        ts_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        bars = await self.get_daily(ts_code, start_date, end_date, limit=10000)
        if not bars:
            return pd.DataFrame()

        data = []
        for bar in bars:
            data.append({
                "ts_code": bar.ts_code,
                "trade_date": bar.trade_date,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
                "amount": float(bar.amount) if bar.amount else None,
                "pct_chg": float(bar.pct_chg) if bar.pct_chg else None,
            })

        df = pd.DataFrame(data)
        df = df.sort_values("trade_date").reset_index(drop=True)
        return df
