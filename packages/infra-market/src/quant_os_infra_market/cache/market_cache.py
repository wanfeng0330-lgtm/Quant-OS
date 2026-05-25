"""Market data caching layer."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

from quant_os_shared.cache.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class MarketCache:
    """Redis caching layer for market data."""

    def __init__(self, redis_cache: RedisCache) -> None:
        self._cache = redis_cache
        self._stock_list_ttl = 3600 * 24  # 24 hours
        self._ohlcv_ttl = 3600 * 4  # 4 hours
        self._calendar_ttl = 3600 * 24 * 7  # 7 days

    async def get_stock_list(self) -> list[dict] | None:
        return await self._cache.get("market:stock_list")

    async def set_stock_list(self, stocks: list[dict]) -> None:
        await self._cache.set("market:stock_list", stocks, ttl=self._stock_list_ttl)

    async def get_ohlcv_daily(self, ts_code: str, start_date: str, end_date: str) -> list[dict] | None:
        key = f"market:ohlcv:{ts_code}:{start_date}:{end_date}"
        return await self._cache.get(key)

    async def set_ohlcv_daily(self, ts_code: str, start_date: str, end_date: str, data: list[dict]) -> None:
        key = f"market:ohlcv:{ts_code}:{start_date}:{end_date}"
        await self._cache.set(key, data, ttl=self._ohlcv_ttl)

    async def get_calendar(self, year: int) -> list[dict] | None:
        return await self._cache.get(f"market:calendar:{year}")

    async def set_calendar(self, year: int, data: list[dict]) -> None:
        await self._cache.set(f"market:calendar:{year}", data, ttl=self._calendar_ttl)

    async def get_latest_sync_date(self, data_type: str) -> str | None:
        return await self._cache.get(f"market:sync_date:{data_type}")

    async def set_latest_sync_date(self, data_type: str, sync_date: str) -> None:
        await self._cache.set(f"market:sync_date:{data_type}", sync_date, ttl=self._calendar_ttl)

    async def invalidate_stock_list(self) -> None:
        await self._cache.delete("market:stock_list")

    async def invalidate_ohlcv(self, ts_code: str | None = None) -> None:
        pattern = f"market:ohlcv:{ts_code}:*" if ts_code else "market:ohlcv:*"
        await self._cache.clear_prefix(pattern)
