"""Unified data service - DB-first with automatic provider sync."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from quant_os_infra_market.providers.base import DataProvider
from quant_os_infra_market.repositories.stock_repo import StockRepository
from quant_os_infra_market.repositories.ohlcv_repo import OHLCVRepository
from quant_os_infra_market.repositories.calendar_repo import TradingCalendarRepository

logger = logging.getLogger(__name__)


class DataService:
    """Single entry point for all market data access.

    Pattern: query DB first → if empty/stale, sync from provider → persist → return.
    All agent tools, factor service, and backtest service should go through this.
    """

    def __init__(self, session: AsyncSession, provider: DataProvider) -> None:
        self._session = session
        self._provider = provider
        self._stock_repo = StockRepository(session)
        self._ohlcv_repo = OHLCVRepository(session)
        self._calendar_repo = TradingCalendarRepository(session)

    # ------------------------------------------------------------------
    # Stock info
    # ------------------------------------------------------------------

    async def get_stock(self, ts_code: str) -> dict | None:
        """Get single stock info. Auto-syncs stock list if DB is empty."""
        stock = await self._stock_repo.get_by_ts_code(ts_code)
        if stock:
            return self._stock_to_dict(stock)

        # DB might be empty — try syncing stock list once
        if await self._stock_repo.count() == 0:
            await self._sync_stock_list()
            stock = await self._stock_repo.get_by_ts_code(ts_code)
            if stock:
                return self._stock_to_dict(stock)

        return None

    async def search_stocks(self, keyword: str, limit: int = 20) -> list[dict]:
        """Search stocks. Auto-syncs if DB is empty."""
        from sqlalchemy import select, or_
        from quant_os_infra_market.models.stock_model import StockModel

        if await self._stock_repo.count() == 0:
            await self._sync_stock_list()

        result = await self._session.execute(
            select(StockModel)
            .where(or_(
                StockModel.ts_code.ilike(f"%{keyword}%"),
                StockModel.symbol.ilike(f"%{keyword}%"),
                StockModel.name.ilike(f"%{keyword}%"),
            ))
            .limit(limit)
        )
        return [self._stock_to_dict(s) for s in result.scalars().all()]

    async def list_stocks(
        self,
        exchange: str | None = None,
        board: str | None = None,
        is_st: bool | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> dict:
        """List stocks with pagination. Auto-syncs if DB is empty."""
        if await self._stock_repo.count() == 0:
            await self._sync_stock_list()

        stocks, total = await self._stock_repo.list_stocks(
            exchange=exchange, board=board, is_st=is_st, status=status,
            offset=(page - 1) * size, limit=size,
        )
        return {
            "items": [self._stock_to_dict(s) for s in stocks],
            "total": total, "page": page, "size": size,
        }

    # ------------------------------------------------------------------
    # OHLCV data
    # ------------------------------------------------------------------

    async def get_ohlcv(
        self,
        ts_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Get OHLCV as DataFrame. Auto-syncs from provider if DB has no data."""
        # Try DB first
        df = await self._ohlcv_repo.get_as_dataframe(ts_code, start_date, end_date)
        if not df.empty:
            return df

        # No data in DB — sync from provider
        await self._sync_ohlcv(ts_code, start_date, end_date)

        # Retry DB
        df = await self._ohlcv_repo.get_as_dataframe(ts_code, start_date, end_date)
        return df

    async def get_ohlcv_for_factor(
        self,
        start_date: date,
        end_date: date,
        stock_pool: list[str] | None = None,
    ) -> pd.DataFrame:
        """Get cross-sectional OHLCV for factor computation.

        Reads from DB. If missing stocks are detected, syncs them incrementally.
        """
        target_codes = stock_pool
        if not target_codes:
            # Use all stocks in DB
            stocks, _ = await self._stock_repo.list_stocks(limit=10000)
            target_codes = [s.ts_code for s in stocks]

        if not target_codes:
            # DB is empty — sync stock list first
            await self._sync_stock_list()
            stocks, _ = await self._stock_repo.list_stocks(limit=10000)
            target_codes = [s.ts_code for s in stocks]

        if not target_codes:
            return pd.DataFrame()

        # Check which stocks need syncing (no data in date range)
        need_sync = []
        for code in target_codes[:200]:  # Cap to avoid too many requests
            latest = await self._ohlcv_repo.get_latest_date(code)
            if not latest or latest < end_date:
                need_sync.append(code)

        # Incremental sync for missing stocks (batch in groups)
        if need_sync:
            logger.info("Auto-syncing OHLCV for %d stocks", len(need_sync))
            for code in need_sync:
                await self._sync_ohlcv(code, start_date, end_date)

        # Now read all from DB
        all_frames = []
        for code in target_codes:
            stock_df = await self._ohlcv_repo.get_as_dataframe(code, start_date, end_date)
            if not stock_df.empty:
                all_frames.append(stock_df)

        if not all_frames:
            return pd.DataFrame()
        return pd.concat(all_frames, ignore_index=True)

    async def get_ohlcv_cross_section(self, trade_date: date) -> pd.DataFrame:
        """Get OHLCV for all stocks on a single date. Auto-syncs if empty."""
        bars = await self._ohlcv_repo.get_daily_cross_section(trade_date)
        if bars:
            return self._bars_to_dataframe(bars)

        # Try syncing from provider
        try:
            df = await self._provider.fetch_ohlcv_daily(trade_date=trade_date)
            if not df.empty:
                records = df.to_dict("records")
                await self._ohlcv_repo.bulk_insert(records)
                bars = await self._ohlcv_repo.get_daily_cross_section(trade_date)
                return self._bars_to_dataframe(bars)
        except Exception as e:
            logger.warning("Failed to auto-sync cross-section OHLCV: %s", e)

        return pd.DataFrame()

    # ------------------------------------------------------------------
    # Trading calendar
    # ------------------------------------------------------------------

    async def get_trading_calendar(self, year: int) -> list[dict]:
        """Get trading calendar. Auto-syncs if DB is empty."""
        from sqlalchemy import select
        from quant_os_infra_market.models.calendar_model import TradingCalendarModel

        result = await self._session.execute(
            select(TradingCalendarModel)
            .where(TradingCalendarModel.cal_date >= f"{year}-01-01")
            .where(TradingCalendarModel.cal_date <= f"{year}-12-31")
            .order_by(TradingCalendarModel.cal_date)
        )
        days = result.scalars().all()
        if days:
            return [{"date": str(d.cal_date), "is_open": d.is_open} for d in days]

        # Auto-sync
        try:
            df = await self._provider.fetch_trading_calendar(year=year)
            if not df.empty:
                records = df.to_dict("records")
                await self._calendar_repo.bulk_upsert(records)
                result = await self._session.execute(
                    select(TradingCalendarModel)
                    .where(TradingCalendarModel.cal_date >= f"{year}-01-01")
                    .where(TradingCalendarModel.cal_date <= f"{year}-12-31")
                    .order_by(TradingCalendarModel.cal_date)
                )
                days = result.scalars().all()
                return [{"date": str(d.cal_date), "is_open": d.is_open} for d in days]
        except Exception as e:
            logger.warning("Failed to auto-sync trading calendar: %s", e)

        return []

    # ------------------------------------------------------------------
    # Internal sync helpers
    # ------------------------------------------------------------------

    async def _sync_stock_list(self) -> None:
        """Fetch stock list from provider and persist to DB."""
        logger.info("Auto-syncing stock list from %s", self._provider.provider_name)
        try:
            df = await self._provider.fetch_stock_list()
            if not df.empty:
                records = df.to_dict("records")
                await self._stock_repo.bulk_upsert(records)
                logger.info("Auto-synced %d stocks to DB", len(records))
        except Exception as e:
            logger.warning("Auto-sync stock list failed: %s", e)

    async def _sync_ohlcv(
        self,
        ts_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> None:
        """Fetch OHLCV from provider with incremental sync and persist."""
        # Incremental: start from latest date in DB
        if not start_date:
            latest = await self._ohlcv_repo.get_latest_date(ts_code)
            if latest:
                start_date = latest + timedelta(days=1)
            else:
                start_date = date(2020, 1, 1)

        if not end_date:
            end_date = datetime.now().date()

        if start_date > end_date:
            return  # Already up to date

        try:
            df = await self._provider.fetch_ohlcv_daily(
                ts_code=ts_code, start_date=start_date, end_date=end_date,
            )
            if not df.empty:
                records = df.to_dict("records")
                await self._ohlcv_repo.bulk_insert(records)
                logger.info("Auto-synced %d OHLCV bars for %s", len(records), ts_code)
        except Exception as e:
            logger.warning("Auto-sync OHLCV failed for %s: %s", ts_code, e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stock_to_dict(stock) -> dict:
        return {
            "ts_code": stock.ts_code,
            "symbol": stock.symbol,
            "name": stock.name,
            "exchange": stock.exchange,
            "board": stock.board,
            "industry": stock.industry,
            "is_st": bool(stock.is_st),
            "is_hs": bool(stock.is_hs),
            "list_date": str(stock.list_date) if stock.list_date else None,
            "total_share": float(stock.total_share) if stock.total_share else None,
            "float_share": float(stock.float_share) if stock.float_share else None,
            "status": stock.status,
        }

    @staticmethod
    def _bars_to_dataframe(bars) -> pd.DataFrame:
        data = [{
            "ts_code": bar.ts_code,
            "trade_date": bar.trade_date,
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
            "amount": float(bar.amount) if bar.amount else None,
            "pct_chg": float(bar.pct_chg) if bar.pct_chg else None,
        } for bar in bars]
        return pd.DataFrame(data).sort_values("trade_date").reset_index(drop=True)
