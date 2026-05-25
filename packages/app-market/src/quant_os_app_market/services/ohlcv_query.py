"""OHLCV query service."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_infra_market.repositories.ohlcv_repo import OHLCVRepository
from quant_os_infra_market.cache.market_cache import MarketCache

logger = logging.getLogger(__name__)


class OHLCVQueryService:
    """Service for querying OHLCV data with caching."""

    def __init__(
        self,
        session: AsyncSession,
        cache: MarketCache | None = None,
    ) -> None:
        self._session = session
        self._cache = cache
        self._repo = OHLCVRepository(session)

    async def get_daily_bars(
        self,
        ts_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        adjust: str = "",
    ) -> list[dict[str, Any]]:
        sd_str = str(start_date) if start_date else ""
        ed_str = str(end_date) if end_date else ""

        if self._cache and adjust == "":
            cached = await self._cache.get_ohlcv_daily(ts_code, sd_str, ed_str)
            if cached is not None:
                return cached

        bars = await self._repo.get_daily(ts_code, start_date, end_date)
        result = [self._bar_to_dict(b) for b in bars]

        if self._cache and adjust == "" and result:
            await self._cache.set_ohlcv_daily(ts_code, sd_str, ed_str, result)

        return result

    async def get_cross_section(self, trade_date: date) -> list[dict[str, Any]]:
        bars = await self._repo.get_daily_cross_section(trade_date)
        return [self._bar_to_dict(b) for b in bars]

    @staticmethod
    def _bar_to_dict(bar) -> dict[str, Any]:
        return {
            "ts_code": bar.ts_code,
            "trade_date": str(bar.trade_date),
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "pre_close": float(bar.pre_close) if bar.pre_close else None,
            "change": float(bar.change) if bar.change else None,
            "pct_chg": float(bar.pct_chg) if bar.pct_chg else None,
            "volume": float(bar.volume),
            "amount": float(bar.amount) if bar.amount else None,
            "turnover_rate": float(bar.turnover_rate) if bar.turnover_rate else None,
            "is_limit_up": bar.is_limit_up,
            "is_limit_down": bar.is_limit_down,
            "is_suspended": bar.is_suspended,
        }
