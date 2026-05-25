"""Data provider protocol interface."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class DataProvider(Protocol):
    """Protocol that all market data providers must implement."""

    @property
    def provider_name(self) -> str:
        """Return the name of this data provider."""
        ...

    async def fetch_stock_list(self) -> pd.DataFrame:
        """Fetch all A-share stock list with basic info.

        Returns DataFrame with columns:
            ts_code, symbol, name, exchange, board, list_date,
            delist_date, industry, is_hs, total_share, float_share
        """
        ...

    async def fetch_ohlcv_daily(
        self,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV data.

        Can query by:
        - Single stock + date range: ts_code + start_date/end_date
        - All stocks on a date: trade_date

        Returns DataFrame with columns:
            ts_code, trade_date, open, high, low, close, pre_close,
            change, pct_chg, volume, amount
        """
        ...

    async def fetch_ohlcv_adj_factor(
        self,
        ts_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch adjustment factors for price adjustment.

        Returns DataFrame with columns:
            ts_code, trade_date, adj_factor
        """
        ...

    async def fetch_financial_report(
        self,
        ts_code: str,
        fiscal_year: int | None = None,
        report_type: str | None = None,
    ) -> pd.DataFrame:
        """Fetch financial report data.

        Returns DataFrame with columns:
            ts_code, report_type, fiscal_year, announce_date, end_date,
            total_revenue, net_profit, net_profit_deducted, eps, roe, roa,
            gross_margin, debt_to_asset, cash_flow_operating, ...
        """
        ...

    async def fetch_dragon_tiger(
        self,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch dragon-tiger list.

        Returns DataFrame with columns:
            ts_code, trade_date, reason, buy_amount, sell_amount,
            net_amount, broker_name, broker_type
        """
        ...

    async def fetch_northbound_flow(
        self,
        ts_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch northbound capital flow.

        Returns DataFrame with columns:
            trade_date, ts_code, channel, buy_amount, sell_amount,
            net_amount, hold_volume, hold_ratio
        """
        ...

    async def fetch_trading_calendar(
        self,
        exchange: str = "SSE",
        year: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch trading calendar.

        Returns DataFrame with columns:
            cal_date, is_open, exchange, pre_trade_date
        """
        ...

    async def fetch_sector_classification(
        self,
        classification: str = "shenwan",
        level: int = 1,
    ) -> pd.DataFrame:
        """Fetch sector/industry classification.

        Returns DataFrame with columns:
            sector_code, sector_name, level, parent_code
        """
        ...

    async def fetch_stock_sector_map(
        self,
        classification: str = "shenwan",
    ) -> pd.DataFrame:
        """Fetch stock-to-sector mapping.

        Returns DataFrame with columns:
            ts_code, sector_code, classification, in_date, out_date
        """
        ...

    async def fetch_daily_basic(
        self,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch daily basic indicators (PE, PB, market cap, etc.).

        Returns DataFrame with columns:
            ts_code, trade_date, pe, pe_ttm, pb, total_mv, circ_mv,
            turnover_rate, turnover_rate_f, volume_ratio
        """
        ...
