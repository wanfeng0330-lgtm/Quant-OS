"""Deterministic local data provider for demos, tests, and offline workflows."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd


class SyntheticProvider:
    """Small deterministic A-share-like provider with no network dependency."""

    provider_name = "synthetic"

    _stocks = [
        ("000001.SZ", "000001", "Ping An Bank", "SZSE", "main"),
        ("000002.SZ", "000002", "Vanke A", "SZSE", "main"),
        ("600000.SH", "600000", "SPDB", "SSE", "main"),
        ("600519.SH", "600519", "Kweichow Moutai", "SSE", "main"),
        ("300750.SZ", "300750", "CATL", "SZSE", "chinext"),
        ("688981.SH", "688981", "SMIC", "SSE", "star"),
    ]

    async def fetch_stock_list(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "ts_code": ts_code,
                    "symbol": symbol,
                    "name": name,
                    "exchange": exchange,
                    "board": board,
                    "list_date": date(2010, 1, 1),
                    "delist_date": None,
                    "industry": "demo",
                    "is_hs": False,
                    "total_share": None,
                    "float_share": None,
                    "is_st": False,
                    "status": "active",
                }
                for ts_code, symbol, name, exchange, board in self._stocks
            ]
        )

    async def fetch_ohlcv_daily(
        self,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        if trade_date:
            dates = [trade_date]
        else:
            start = start_date or date(2024, 1, 2)
            end = end_date or datetime.now().date()
            dates = [d.date() for d in pd.bdate_range(start, end)]

        codes = [ts_code] if ts_code else [item[0] for item in self._stocks]
        rows = []
        for code_index, code in enumerate(codes):
            base = 10.0 + code_index * 5
            for index, current_date in enumerate(dates):
                drift = index * (0.03 + code_index * 0.004)
                cycle = np.sin(index / 3 + code_index) * 0.15
                close = round(base + drift + cycle, 4)
                open_price = round(close * (1 + np.sin(index + code_index) * 0.002), 4)
                high = round(max(open_price, close) * 1.01, 4)
                low = round(min(open_price, close) * 0.99, 4)
                pre_close = rows[-1]["close"] if rows and rows[-1]["ts_code"] == code else close
                pct_chg = (close / pre_close - 1) * 100 if pre_close else 0.0
                volume = 100000 + code_index * 8000 + index * 750
                rows.append(
                    {
                        "ts_code": code,
                        "trade_date": current_date,
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "close": close,
                        "pre_close": pre_close,
                        "change": close - pre_close,
                        "pct_chg": pct_chg,
                        "volume": float(volume),
                        "amount": float(volume * close),
                        "turnover_rate": 1.0 + code_index * 0.1,
                        "is_limit_up": False,
                        "is_limit_down": False,
                        "is_suspended": False,
                    }
                )
        return pd.DataFrame(rows)

    async def fetch_ohlcv_adj_factor(
        self,
        ts_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        bars = await self.fetch_ohlcv_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if bars.empty:
            return pd.DataFrame(columns=["ts_code", "trade_date", "adj_factor"])
        return bars[["ts_code", "trade_date"]].assign(adj_factor=1.0)

    async def fetch_financial_report(self, ts_code: str, fiscal_year: int | None = None, report_type: str | None = None) -> pd.DataFrame:
        year = fiscal_year or datetime.now().year - 1
        return pd.DataFrame(
            [
                {
                    "ts_code": ts_code,
                    "report_type": report_type or "Annual",
                    "fiscal_year": year,
                    "announce_date": date(year + 1, 4, 30),
                    "end_date": date(year, 12, 31),
                    "total_revenue": 1_000_000_000.0,
                    "net_profit": 120_000_000.0,
                    "eps": 1.2,
                    "roe": 0.12,
                }
            ]
        )

    async def fetch_dragon_tiger(self, trade_date: date | None = None, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        return pd.DataFrame()

    async def fetch_northbound_flow(self, ts_code: str | None = None, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        return pd.DataFrame()

    async def fetch_trading_calendar(
        self,
        exchange: str = "SSE",
        year: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        yr = year or datetime.now().year
        start = start_date or date(yr, 1, 1)
        end = end_date or date(yr, 12, 31)
        days = pd.date_range(start, end, freq="D")
        return pd.DataFrame(
            {
                "cal_date": [d.date() for d in days],
                "is_open": [d.weekday() < 5 for d in days],
                "exchange": exchange,
                "pre_trade_date": None,
            }
        )

    async def fetch_sector_classification(self, classification: str = "shenwan", level: int = 1) -> pd.DataFrame:
        return pd.DataFrame(
            [{"sector_code": "demo", "sector_name": "Demo Sector", "level": level, "parent_code": None}]
        )

    async def fetch_stock_sector_map(self, classification: str = "shenwan") -> pd.DataFrame:
        return pd.DataFrame(
            [{"ts_code": item[0], "sector_code": "demo", "classification": "demo", "in_date": None, "out_date": None} for item in self._stocks]
        )

    async def fetch_daily_basic(
        self,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        codes = [ts_code] if ts_code else [item[0] for item in self._stocks]
        return pd.DataFrame(
            [
                {
                    "ts_code": code,
                    "trade_date": trade_date or datetime.now().date(),
                    "pe": 15.0,
                    "pe_ttm": 16.0,
                    "pb": 1.8,
                    "total_mv": 100_000_000.0,
                    "circ_mv": 80_000_000.0,
                    "turnover_rate": 1.2,
                    "turnover_rate_f": 1.1,
                    "volume_ratio": 1.0,
                }
                for code in codes
            ]
        )
