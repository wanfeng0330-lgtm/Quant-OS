"""Tushare data provider implementation."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from functools import partial
from typing import Any

import pandas as pd

from quant_os_shared.errors import DataProviderError

logger = logging.getLogger(__name__)


class TushareProvider:
    """Market data provider using Tushare Pro API (requires token)."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._api = None

    @property
    def provider_name(self) -> str:
        return "tushare"

    def _get_api(self):
        if self._api is None:
            import tushare as ts
            ts.set_token(self._token)
            self._api = ts.pro_api()
        return self._api

    async def _run_sync(self, func, *args, **kwargs) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def fetch_stock_list(self) -> pd.DataFrame:
        api = self._get_api()
        try:
            df = await self._run_sync(api.stock_basic, exchange="", list_status="L",
                                       fields="ts_code,symbol,name,area,industry,list_date,delist_date,is_hs")

            result = pd.DataFrame()
            result["ts_code"] = df["ts_code"]
            result["symbol"] = df["symbol"]
            result["name"] = df["name"]
            result["exchange"] = df["ts_code"].apply(lambda x: x.split(".")[-1] if "." in x else "")
            result["board"] = df["ts_code"].apply(self._get_board)
            result["list_date"] = pd.to_datetime(df["list_date"], format="%Y%m%d", errors="coerce").dt.date
            result["delist_date"] = pd.to_datetime(df.get("delist_date", pd.Series(dtype=str)), format="%Y%m%d", errors="coerce").dt.date
            result["industry"] = df.get("industry", "")
            result["is_hs"] = df.get("is_hs", "N") == "Y"
            result["total_share"] = None
            result["float_share"] = None
            result["is_st"] = df["name"].str.contains("ST", case=False, na=False)
            result["status"] = "active"

            logger.info("Fetched %d stocks from Tushare", len(result))
            return result

        except Exception as exc:
            logger.error("Failed to fetch stock list from Tushare: %s", exc)
            raise DataProviderError(f"Tushare stock list fetch failed: {exc}") from exc

    async def fetch_ohlcv_daily(
        self,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        api = self._get_api()
        try:
            kwargs: dict[str, Any] = {}
            if ts_code:
                kwargs["ts_code"] = ts_code
            if trade_date:
                kwargs["trade_date"] = trade_date.strftime("%Y%m%d")
            if start_date:
                kwargs["start_date"] = start_date.strftime("%Y%m%d")
            if end_date:
                kwargs["end_date"] = end_date.strftime("%Y%m%d")

            df = await self._run_sync(api.daily, **kwargs)

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["ts_code"] = df["ts_code"]
            result["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.date
            result["open"] = df["open"].astype(float)
            result["high"] = df["high"].astype(float)
            result["low"] = df["low"].astype(float)
            result["close"] = df["close"].astype(float)
            result["pre_close"] = df["pre_close"].astype(float)
            result["change"] = df["change"].astype(float)
            result["pct_chg"] = df["pct_chg"].astype(float)
            result["volume"] = df["vol"].astype(float)
            result["amount"] = df["amount"].astype(float)
            result["turnover_rate"] = None
            result["is_limit_up"] = False
            result["is_limit_down"] = False
            result["is_suspended"] = False

            logger.info("Fetched %d OHLCV daily bars from Tushare", len(result))
            return result

        except Exception as exc:
            logger.error("Failed to fetch OHLCV daily from Tushare: %s", exc)
            raise DataProviderError(f"Tushare OHLCV daily fetch failed: {exc}") from exc

    async def fetch_ohlcv_adj_factor(
        self,
        ts_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        api = self._get_api()
        try:
            kwargs: dict[str, Any] = {"ts_code": ts_code}
            if start_date:
                kwargs["start_date"] = start_date.strftime("%Y%m%d")
            if end_date:
                kwargs["end_date"] = end_date.strftime("%Y%m%d")

            df = await self._run_sync(api.adj_factor, **kwargs)

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["ts_code"] = df["ts_code"]
            result["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.date
            result["adj_factor"] = df["adj_factor"].astype(float)

            return result

        except Exception as exc:
            logger.error("Failed to fetch adj factor from Tushare: %s", exc)
            raise DataProviderError(f"Tushare adj factor fetch failed: {exc}") from exc

    async def fetch_financial_report(
        self,
        ts_code: str,
        fiscal_year: int | None = None,
        report_type: str | None = None,
    ) -> pd.DataFrame:
        api = self._get_api()
        try:
            kwargs: dict[str, Any] = {"ts_code": ts_code}
            if fiscal_year:
                kwargs["period"] = f"{fiscal_year}1231" if report_type == "Annual" else f"{fiscal_year}0331"

            df = await self._run_sync(api.income, **kwargs)

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["ts_code"] = df["ts_code"]
            result["fiscal_year"] = df["end_date"].str[:4].astype(int)
            result["end_date"] = pd.to_datetime(df["end_date"], format="%Y%m%d", errors="coerce").dt.date
            result["announce_date"] = pd.to_datetime(df.get("ann_date", pd.Series(dtype=str)), format="%Y%m%d", errors="coerce").dt.date
            result["total_revenue"] = pd.to_numeric(df.get("revenue", pd.Series(dtype=float)), errors="coerce")
            result["net_profit"] = pd.to_numeric(df.get("n_income", pd.Series(dtype=float)), errors="coerce")
            result["eps"] = None
            result["roe"] = None
            result["report_type"] = "Annual"

            logger.info("Fetched %d financial reports from Tushare for %s", len(result), ts_code)
            return result

        except Exception as exc:
            logger.error("Failed to fetch financial reports from Tushare: %s", exc)
            raise DataProviderError(f"Tushare financial report fetch failed: {exc}") from exc

    async def fetch_dragon_tiger(
        self,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        api = self._get_api()
        try:
            kwargs: dict[str, Any] = {}
            if trade_date:
                kwargs["trade_date"] = trade_date.strftime("%Y%m%d")
            elif start_date:
                kwargs["start_date"] = start_date.strftime("%Y%m%d")
                if end_date:
                    kwargs["end_date"] = end_date.strftime("%Y%m%d")

            df = await self._run_sync(api.top_list, **kwargs)

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["ts_code"] = df["ts_code"]
            result["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.date
            result["reason"] = df.get("reason", "")
            result["buy_amount"] = pd.to_numeric(df.get("buy", pd.Series(dtype=float)), errors="coerce")
            result["sell_amount"] = pd.to_numeric(df.get("sell", pd.Series(dtype=float)), errors="coerce")
            result["net_amount"] = result["buy_amount"] - result["sell_amount"].fillna(0)
            result["broker_name"] = ""
            result["broker_type"] = "buy"

            logger.info("Fetched %d dragon-tiger entries from Tushare", len(result))
            return result

        except Exception as exc:
            logger.error("Failed to fetch dragon-tiger from Tushare: %s", exc)
            raise DataProviderError(f"Tushare dragon-tiger fetch failed: {exc}") from exc

    async def fetch_northbound_flow(
        self,
        ts_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        api = self._get_api()
        try:
            kwargs: dict[str, Any] = {}
            if ts_code:
                kwargs["ts_code"] = ts_code
            if start_date:
                kwargs["start_date"] = start_date.strftime("%Y%m%d")
            if end_date:
                kwargs["end_date"] = end_date.strftime("%Y%m%d")

            df = await self._run_sync(api.hsgt_top10, **kwargs)

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["ts_code"] = df.get("ts_code", None)
            result["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.date
            result["channel"] = df.get("hsgt", "all")
            result["buy_amount"] = pd.to_numeric(df.get("buy", pd.Series(dtype=float)), errors="coerce")
            result["sell_amount"] = pd.to_numeric(df.get("sell", pd.Series(dtype=float)), errors="coerce")
            result["net_amount"] = pd.to_numeric(df.get("net_buy", pd.Series(dtype=float)), errors="coerce")
            result["hold_volume"] = None
            result["hold_ratio"] = None

            logger.info("Fetched %d northbound flow records from Tushare", len(result))
            return result

        except Exception as exc:
            logger.error("Failed to fetch northbound flow from Tushare: %s", exc)
            raise DataProviderError(f"Tushare northbound flow fetch failed: {exc}") from exc

    async def fetch_trading_calendar(
        self,
        exchange: str = "SSE",
        year: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        api = self._get_api()
        try:
            kwargs: dict[str, Any] = {"exchange": exchange}
            if start_date:
                kwargs["start_date"] = start_date.strftime("%Y%m%d")
            else:
                yr = year or datetime.now().year
                kwargs["start_date"] = f"{yr}0101"
            if end_date:
                kwargs["end_date"] = end_date.strftime("%Y%m%d")
            else:
                yr = year or datetime.now().year
                kwargs["end_date"] = f"{yr}1231"

            df = await self._run_sync(api.trade_cal, **kwargs)

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["cal_date"] = pd.to_datetime(df["cal_date"], format="%Y%m%d").dt.date
            result["is_open"] = df["is_open"].astype(bool)
            result["exchange"] = exchange
            result["pre_trade_date"] = pd.to_datetime(df["pretrade_date"], format="%Y%m%d", errors="coerce").dt.date

            logger.info("Fetched trading calendar from Tushare (%d trading days)", result["is_open"].sum())
            return result

        except Exception as exc:
            logger.error("Failed to fetch trading calendar from Tushare: %s", exc)
            raise DataProviderError(f"Tushare trading calendar fetch failed: {exc}") from exc

    async def fetch_sector_classification(
        self,
        classification: str = "shenwan",
        level: int = 1,
    ) -> pd.DataFrame:
        logger.warning("Tushare sector classification not yet implemented, use AKShare")
        return pd.DataFrame()

    async def fetch_stock_sector_map(
        self,
        classification: str = "shenwan",
    ) -> pd.DataFrame:
        logger.warning("Tushare stock-sector map not yet implemented, use AKShare")
        return pd.DataFrame()

    async def fetch_daily_basic(
        self,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        api = self._get_api()
        try:
            kwargs: dict[str, Any] = {}
            if ts_code:
                kwargs["ts_code"] = ts_code
            if trade_date:
                kwargs["trade_date"] = trade_date.strftime("%Y%m%d")
            if start_date:
                kwargs["start_date"] = start_date.strftime("%Y%m%d")
            if end_date:
                kwargs["end_date"] = end_date.strftime("%Y%m%d")

            df = await self._run_sync(api.daily_basic, **kwargs)

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["ts_code"] = df["ts_code"]
            result["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.date
            result["pe"] = pd.to_numeric(df.get("pe", pd.Series(dtype=float)), errors="coerce")
            result["pe_ttm"] = pd.to_numeric(df.get("pe_ttm", pd.Series(dtype=float)), errors="coerce")
            result["pb"] = pd.to_numeric(df.get("pb", pd.Series(dtype=float)), errors="coerce")
            result["total_mv"] = pd.to_numeric(df.get("total_mv", pd.Series(dtype=float)), errors="coerce")
            result["circ_mv"] = pd.to_numeric(df.get("circ_mv", pd.Series(dtype=float)), errors="coerce")
            result["turnover_rate"] = pd.to_numeric(df.get("turnover_rate", pd.Series(dtype=float)), errors="coerce")
            result["turnover_rate_f"] = pd.to_numeric(df.get("turnover_rate_f", pd.Series(dtype=float)), errors="coerce")
            result["volume_ratio"] = pd.to_numeric(df.get("volume_ratio", pd.Series(dtype=float)), errors="coerce")

            return result

        except Exception as exc:
            logger.error("Failed to fetch daily basic from Tushare: %s", exc)
            raise DataProviderError(f"Tushare daily basic fetch failed: {exc}") from exc

    @staticmethod
    def _get_board(ts_code: str) -> str:
        symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
        if symbol.startswith("60"):
            return "main"
        elif symbol.startswith("00"):
            return "main"
        elif symbol.startswith("30"):
            return "chinext"
        elif symbol.startswith("68"):
            return "star"
        elif symbol.startswith(("43", "83", "87")):
            return "bse"
        return "main"
