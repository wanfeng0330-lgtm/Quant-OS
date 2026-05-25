"""Data ingestion service - orchestrates data fetching and storage."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_infra_market.providers.base import DataProvider
from quant_os_infra_market.repositories.stock_repo import StockRepository
from quant_os_infra_market.repositories.ohlcv_repo import OHLCVRepository
from quant_os_infra_market.repositories.calendar_repo import TradingCalendarRepository
from quant_os_infra_market.cache.market_cache import MarketCache
from quant_os_shared.errors import DataSyncError

logger = logging.getLogger(__name__)


class DataIngestionService:
    """Orchestrates market data fetching, validation, and storage."""

    def __init__(
        self,
        session: AsyncSession,
        provider: DataProvider,
        cache: MarketCache | None = None,
    ) -> None:
        self._session = session
        self._provider = provider
        self._cache = cache
        self._stock_repo = StockRepository(session)
        self._ohlcv_repo = OHLCVRepository(session)
        self._calendar_repo = TradingCalendarRepository(session)

    async def sync_stock_list(self) -> dict[str, Any]:
        """Sync the complete A-share stock list."""
        logger.info("Starting stock list sync from %s", self._provider.provider_name)

        df = await self._provider.fetch_stock_list()

        if df.empty:
            raise DataSyncError("Provider returned empty stock list")

        records = df.to_dict("records")
        upserted = await self._stock_repo.bulk_upsert(records)

        if self._cache:
            await self._cache.invalidate_stock_list()
            stock_list = []
            stocks, _ = await self._stock_repo.list_stocks(limit=10000)
            for s in stocks:
                stock_list.append({
                    "ts_code": s.ts_code, "symbol": s.symbol, "name": s.name,
                    "exchange": s.exchange, "board": s.board, "industry": s.industry,
                    "is_st": s.is_st, "status": s.status,
                })
            await self._cache.set_stock_list(stock_list)

        total = await self._stock_repo.count()
        logger.info("Stock list sync complete: %d upserted, %d total", upserted, total)

        return {"upserted": upserted, "total": total, "provider": self._provider.provider_name}

    async def sync_ohlcv_daily(
        self,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Sync daily OHLCV data with incremental update support."""
        logger.info("Starting OHLCV daily sync from %s", self._provider.provider_name)

        if ts_code and not start_date:
            latest = await self._ohlcv_repo.get_latest_date(ts_code)
            if latest:
                start_date = latest + timedelta(days=1)
            else:
                start_date = date(2020, 1, 1)

        if not end_date:
            end_date = datetime.now().date()

        if start_date and start_date > end_date:
            logger.info("Data already up to date for %s", ts_code)
            return {"inserted": 0, "message": "Already up to date"}

        df = await self._provider.fetch_ohlcv_daily(
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            logger.info("No new OHLCV data returned")
            return {"inserted": 0, "message": "No new data"}

        df = self._validate_ohlcv(df)

        records = df.to_dict("records")
        for r in records:
            if isinstance(r.get("trade_date"), date):
                pass
            elif isinstance(r.get("trade_date"), str):
                r["trade_date"] = datetime.strptime(r["trade_date"], "%Y-%m-%d").date()

        inserted = await self._ohlcv_repo.bulk_insert(records)

        if self._cache and ts_code:
            await self._cache.invalidate_ohlcv(ts_code)

        logger.info("OHLCV daily sync complete: %d inserted", inserted)
        return {"inserted": inserted, "provider": self._provider.provider_name}

    async def sync_ohlcv_all_stocks(self, trade_date: date) -> dict[str, Any]:
        """Sync OHLCV for all stocks on a specific date."""
        logger.info("Starting full market OHLCV sync for %s", trade_date)

        df = await self._provider.fetch_ohlcv_daily(trade_date=trade_date)

        if df.empty:
            return {"inserted": 0, "message": "No data for date"}

        df = self._validate_ohlcv(df)
        records = df.to_dict("records")
        inserted = await self._ohlcv_repo.bulk_insert(records)

        logger.info("Full market sync complete for %s: %d inserted", trade_date, inserted)
        return {"inserted": inserted, "trade_date": str(trade_date)}

    async def sync_trading_calendar(self, year: int | None = None) -> dict[str, Any]:
        """Sync the trading calendar."""
        yr = year or datetime.now().year
        logger.info("Starting trading calendar sync for %d", yr)

        df = await self._provider.fetch_trading_calendar(year=yr)

        if df.empty:
            raise DataSyncError("Provider returned empty trading calendar")

        records = df.to_dict("records")
        upserted = await self._calendar_repo.bulk_upsert(records)

        if self._cache:
            cal_data = [{"date": str(r["cal_date"]), "is_open": r["is_open"]} for r in records]
            await self._cache.set_calendar(yr, cal_data)

        logger.info("Trading calendar sync complete: %d upserted", upserted)
        return {"upserted": upserted, "year": yr}

    async def sync_northbound_flow(
        self,
        ts_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Sync northbound capital flow data."""
        from quant_os_infra_market.models.northbound_model import NorthboundFlowModel

        logger.info("Starting northbound flow sync")

        df = await self._provider.fetch_northbound_flow(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            return {"inserted": 0, "message": "No data"}

        records = df.to_dict("records")
        inserted = 0
        for r in records:
            trade_date = r.get("trade_date")
            if not trade_date:
                continue
            # Fix nan values - ts_code can be NaN from DataFrame None
            ts_code = r.get("ts_code")
            if ts_code is not None and str(ts_code) == "nan":
                ts_code = None
            model = NorthboundFlowModel(
                trade_date=trade_date,
                ts_code=str(ts_code) if ts_code else None,
                channel=r.get("channel", "all"),
                buy_amount=r.get("buy_amount") if str(r.get("buy_amount")) != "nan" else None,
                sell_amount=r.get("sell_amount") if str(r.get("sell_amount")) != "nan" else None,
                net_amount=r.get("net_amount") if str(r.get("net_amount")) != "nan" else None,
                hold_volume=r.get("hold_volume") if str(r.get("hold_volume")) != "nan" else None,
                hold_ratio=r.get("hold_ratio") if str(r.get("hold_ratio")) != "nan" else None,
            )
            self._session.add(model)
            inserted += 1

        await self._session.flush()
        logger.info("Northbound flow sync complete: %d inserted", inserted)
        return {"inserted": inserted, "provider": self._provider.provider_name}

    async def sync_dragon_tiger(
        self,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Sync dragon-tiger list data."""
        from quant_os_infra_market.models.dragon_tiger_model import DragonTigerModel

        logger.info("Starting dragon-tiger sync")

        df = await self._provider.fetch_dragon_tiger(
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            return {"inserted": 0, "message": "No data"}

        records = df.to_dict("records")
        inserted = 0
        for r in records:
            ts_code = r.get("ts_code")
            trade_date_val = r.get("trade_date")
            if not ts_code or not trade_date_val:
                continue
            model = DragonTigerModel(
                ts_code=str(ts_code),
                name=str(r.get("name", ""))[:50] if r.get("name") else None,
                trade_date=trade_date_val,
                reason=str(r.get("reason", ""))[:200] if r.get("reason") else None,
                buy_amount=r.get("buy_amount"),
                sell_amount=r.get("sell_amount"),
                net_amount=r.get("net_amount"),
                broker_name=str(r.get("broker_name", ""))[:200] if r.get("broker_name") else None,
                broker_type=r.get("broker_type", "buy"),
            )
            self._session.add(model)
            inserted += 1

        await self._session.flush()
        logger.info("Dragon-tiger sync complete: %d inserted", inserted)
        return {"inserted": inserted, "provider": self._provider.provider_name}

    async def sync_sector_classification(self) -> dict[str, Any]:
        """Sync sector/industry classification."""
        logger.info("Starting sector classification sync")

        df = await self._provider.fetch_sector_classification()

        if df.empty:
            return {"inserted": 0, "message": "No data"}

        return {"fetched": len(df), "provider": self._provider.provider_name}

    def _validate_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean OHLCV data."""
        required_cols = ["ts_code", "trade_date", "open", "high", "low", "close", "volume"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise DataSyncError(f"OHLCV data missing columns: {missing}")

        # Ensure ts_code is always a clean string (NaN from DataFrame -> float)
        df = df[df["ts_code"].notna()]
        df["ts_code"] = df["ts_code"].astype(str)
        df = df[df["ts_code"] != "nan"]
        df = df.dropna(subset=["close"])
        df = df[df["close"] > 0]
        df = df[df["volume"] >= 0]

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["open", "high", "low", "close"])

        logger.debug("OHLCV validation: %d rows after cleaning", len(df))
        return df
