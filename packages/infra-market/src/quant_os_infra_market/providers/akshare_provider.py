"""AKShare data provider implementation."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta
from functools import partial
from typing import Any

import pandas as pd

from quant_os_shared.errors import DataProviderError, DataNotFoundError

logger = logging.getLogger(__name__)

# Rate limiting: minimum seconds between AKShare calls
_last_call_time: float = 0.0
_RATE_LIMIT_INTERVAL: float = 0.5  # 500ms between calls


class AKShareProvider:
    """Market data provider using AKShare (free, open-source).

    AKShare is a synchronous library, so all blocking calls are dispatched
    to the default asyncio thread-pool executor via ``_run_sync``.  Every
    public method normalises its return value to the column schema defined
    by the ``DataProvider`` protocol so that downstream code stays
    provider-agnostic.
    """

    # ------------------------------------------------------------------
    # Protocol identity
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "akshare"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_sync(self, func, *args, **kwargs) -> Any:
        """Run a synchronous function in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def _run_with_retry(self, func, *args, max_retries: int = 3, **kwargs) -> Any:
        """Run a synchronous function with rate limiting and retry on connection errors."""
        global _last_call_time
        for attempt in range(max_retries):
            # Rate limiting
            now = time.monotonic()
            elapsed = now - _last_call_time
            if elapsed < _RATE_LIMIT_INTERVAL:
                await asyncio.sleep(_RATE_LIMIT_INTERVAL - elapsed)
            _last_call_time = time.monotonic()

            try:
                return await self._run_sync(func, *args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                is_retryable = any(kw in error_str for kw in (
                    "connectionaborted", "remotedisconnected", "connectionreset",
                    "connectionerror", "timeout", "toomanyrequests",
                ))
                if is_retryable and attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning("AKShare call failed (attempt %d/%d), retrying in %ds: %s",
                                   attempt + 1, max_retries, wait, e)
                    await asyncio.sleep(wait)
                    continue
                raise

    @staticmethod
    def _to_ts_code(code: str) -> str:
        """Convert a numeric stock code to ``<code>.<EXCHANGE>`` format.

        Rules (matching A-share conventions):
        - Codes starting with 6 or 9 -> Shanghai (.SH)
        - Codes starting with 0, 3, or 2 -> Shenzhen (.SZ)
        - Codes starting with 4 or 8 -> Beijing (.BJ)
        """
        code = str(code).strip()
        if "." in code:
            return code
        if code.startswith(("6", "9")):
            return f"{code}.SH"
        elif code.startswith(("0", "3", "2")):
            return f"{code}.SZ"
        elif code.startswith(("4", "8")):
            return f"{code}.BJ"
        return f"{code}.SZ"

    @staticmethod
    def _get_exchange(code: str) -> str:
        """Derive the exchange name from a numeric stock code."""
        symbol = code.split(".")[0] if "." in code else code
        if symbol.startswith(("6", "9")):
            return "SSE"
        elif symbol.startswith(("0", "3", "2")):
            return "SZSE"
        elif symbol.startswith(("4", "8")):
            return "BSE"
        return "SZSE"

    @staticmethod
    def _get_board(code: str) -> str:
        """Determine the board type from a numeric stock code.

        Returns one of: main, chinext, star, bse.
        """
        symbol = code.split(".")[0] if "." in code else code
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

    @staticmethod
    def _get_exchange_prefix(ts_code: str) -> str:
        """Return the lowercase exchange prefix used by AKShare symbols."""
        if ts_code.endswith(".SH"):
            return "sh"
        elif ts_code.endswith(".SZ"):
            return "sz"
        elif ts_code.endswith(".BJ"):
            return "bj"
        return "sz"

    # ------------------------------------------------------------------
    # DataProvider interface implementation
    # ------------------------------------------------------------------

    async def fetch_stock_list(self) -> pd.DataFrame:
        """Fetch the full A-share stock list with basic metadata.

        Uses ``ak.stock_info_a_code_name()`` which returns all active
        A-share codes and names.  Additional fields (industry, share
        counts, etc.) are left as ``None`` because this particular AKShare
        endpoint does not supply them; enrich from other endpoints as
        needed.
        """
        import akshare as ak

        try:
            df = await self._run_with_retry(ak.stock_info_a_code_name)

            result = pd.DataFrame()
            result["ts_code"] = df["code"].apply(self._to_ts_code)
            result["symbol"] = df["code"]
            result["name"] = df["name"]
            result["exchange"] = df["code"].apply(self._get_exchange)
            result["board"] = df["code"].apply(self._get_board)
            result["list_date"] = None
            result["delist_date"] = None
            result["industry"] = None
            result["is_hs"] = False
            result["total_share"] = None
            result["float_share"] = None
            result["is_st"] = df["name"].str.contains("ST", case=False, na=False)
            result["status"] = "active"

            logger.info("Fetched %d stocks from AKShare", len(result))
            return result

        except Exception as exc:
            logger.error("Failed to fetch stock list from AKShare: %s", exc)
            raise DataProviderError(f"AKShare stock list fetch failed: {exc}") from exc

    async def fetch_ohlcv_daily(
        self,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars.

        Two access patterns are supported:

        1. **Single stock, date range** -- ``ts_code`` + ``start_date`` /
           ``end_date``.  Calls ``ak.stock_zh_a_hist`` which returns
           historical bars for one symbol.

        2. **All stocks, single date** -- ``trade_date``.  Calls
           ``ak.stock_zh_a_spot_em`` which returns a real-time snapshot
           of every A-share; this is used as a proxy for "all stocks on
           a given day".
        """
        import akshare as ak

        try:
            # ----- Single stock + date range -----
            if ts_code and (start_date or end_date):
                symbol = ts_code.split(".")[0]
                sd = start_date.strftime("%Y%m%d") if start_date else "20200101"
                ed = end_date.strftime("%Y%m%d") if end_date else datetime.now().strftime("%Y%m%d")

                df = await self._run_with_retry(
                    ak.stock_zh_a_hist,
                    symbol=symbol,
                    period="daily",
                    start_date=sd,
                    end_date=ed,
                    adjust="",
                )

                if df.empty:
                    return pd.DataFrame()

                result = pd.DataFrame()
                result["ts_code"] = ts_code
                result["trade_date"] = pd.to_datetime(df["日期"]).dt.date
                result["open"] = df["开盘"].astype(float)
                result["high"] = df["最高"].astype(float)
                result["low"] = df["最低"].astype(float)
                result["close"] = df["收盘"].astype(float)
                result["pre_close"] = None
                result["change"] = df.get("涨跌额", pd.Series(dtype=float)).astype(float)
                result["pct_chg"] = df.get("涨跌幅", pd.Series(dtype=float)).astype(float)
                result["volume"] = df["成交量"].astype(float)
                result["amount"] = df["成交额"].astype(float) / 1000  # Convert to 千元
                result["turnover_rate"] = df.get("换手率", pd.Series(dtype=float)).astype(float)
                result["is_limit_up"] = False
                result["is_limit_down"] = False
                result["is_suspended"] = False

                # Detect limit up/down (10% for main board, 20% for chinext/star)
                if "pct_chg" in result.columns:
                    board = self._get_board(ts_code)
                    limit = 0.20 if board in ("chinext", "star") else 0.10
                    result["is_limit_up"] = result["pct_chg"] >= limit * 100 - 0.01
                    result["is_limit_down"] = result["pct_chg"] <= -limit * 100 + 0.01

                logger.info("Fetched %d OHLCV daily bars for %s", len(result), ts_code)
                return result

            # ----- All stocks on a single date -----
            elif trade_date:
                df = await self._run_with_retry(ak.stock_zh_a_spot_em)

                if df.empty:
                    return pd.DataFrame()

                result = pd.DataFrame()
                result["ts_code"] = df["代码"].apply(self._to_ts_code)
                result["trade_date"] = trade_date
                result["open"] = pd.to_numeric(df["今开"], errors="coerce")
                result["high"] = pd.to_numeric(df["最高"], errors="coerce")
                result["low"] = pd.to_numeric(df["最低"], errors="coerce")
                result["close"] = pd.to_numeric(df["最新价"], errors="coerce")
                result["pre_close"] = pd.to_numeric(df["昨收"], errors="coerce")
                result["change"] = pd.to_numeric(df["涨跌额"], errors="coerce")
                result["pct_chg"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
                result["volume"] = pd.to_numeric(df["成交量"], errors="coerce")
                result["amount"] = pd.to_numeric(df["成交额"], errors="coerce") / 1000
                result["turnover_rate"] = pd.to_numeric(
                    df.get("换手率", pd.Series(dtype=float)), errors="coerce"
                )
                result["is_limit_up"] = False
                result["is_limit_down"] = False
                result["is_suspended"] = False

                logger.info("Fetched %d stocks for date %s", len(result), trade_date)
                return result
            else:
                raise DataProviderError(
                    "Must provide either ts_code+date_range or trade_date"
                )

        except DataProviderError:
            raise
        except Exception as exc:
            logger.error("Failed to fetch OHLCV daily from AKShare: %s", exc)
            raise DataProviderError(f"AKShare OHLCV daily fetch failed: {exc}") from exc

    async def fetch_ohlcv_adj_factor(
        self,
        ts_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch price adjustment factors.

        Uses ``ak.stock_zh_a_daily`` with ``adjust="hfq"`` (forward
        adjustment).  The returned ``adjust`` column serves as the
        adjustment factor that can be applied to raw OHLCV prices.
        """
        import akshare as ak

        try:
            symbol = ts_code.split(".")[0]
            df = await self._run_with_retry(
                ak.stock_zh_a_daily,
                symbol=f"{self._get_exchange_prefix(ts_code)}{symbol}",
                adjust="hfq",
            )

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["ts_code"] = ts_code
            result["trade_date"] = pd.to_datetime(df["date"]).dt.date
            result["adj_factor"] = df.get("adjust", pd.Series([1.0] * len(df)))

            return result

        except Exception as exc:
            logger.error("Failed to fetch adj factor from AKShare: %s", exc)
            raise DataProviderError(f"AKShare adj factor fetch failed: {exc}") from exc

    async def fetch_financial_report(
        self,
        ts_code: str,
        fiscal_year: int | None = None,
        report_type: str | None = None,
    ) -> pd.DataFrame:
        """Fetch financial report summary data.

        Uses ``ak.stock_financial_abstract`` which provides a high-level
        financial summary per stock.  When ``fiscal_year`` or
        ``report_type`` are supplied the result is filtered accordingly.
        """
        import akshare as ak

        try:
            symbol = ts_code.split(".")[0]
            df = await self._run_with_retry(ak.stock_financial_abstract, symbol=symbol)

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["ts_code"] = ts_code
            result["report_type"] = df.get("报告类型", "Annual")
            result["fiscal_year"] = pd.to_datetime(
                df.get("报告日期", pd.Series(dtype=str)), errors="coerce"
            ).dt.year
            result["announce_date"] = pd.to_datetime(
                df.get("公告日期", pd.Series(dtype=str)), errors="coerce"
            ).dt.date
            result["end_date"] = pd.to_datetime(
                df.get("报告日期", pd.Series(dtype=str)), errors="coerce"
            ).dt.date
            result["total_revenue"] = pd.to_numeric(
                df.get("营业总收入", pd.Series(dtype=float)), errors="coerce"
            )
            result["net_profit"] = pd.to_numeric(
                df.get("归母净利润", pd.Series(dtype=float)), errors="coerce"
            )
            result["eps"] = pd.to_numeric(
                df.get("基本每股收益", pd.Series(dtype=float)), errors="coerce"
            )
            result["roe"] = pd.to_numeric(
                df.get("加权净资产收益率", pd.Series(dtype=float)), errors="coerce"
            )

            # Optional filtering
            if fiscal_year is not None:
                result = result[result["fiscal_year"] == fiscal_year]
            if report_type is not None:
                result = result[result["report_type"] == report_type]

            logger.info("Fetched %d financial reports for %s", len(result), ts_code)
            return result

        except Exception as exc:
            logger.error("Failed to fetch financial reports from AKShare: %s", exc)
            raise DataProviderError(f"AKShare financial report fetch failed: {exc}") from exc

    async def fetch_dragon_tiger(
        self,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch the dragon-tiger list (longhu bang / LHB).

        Uses ``ak.stock_lhb_detail_em``.  When no date parameters are
        provided the query defaults to the most recent 7 days.
        """
        import akshare as ak

        try:
            if trade_date:
                date_str = trade_date.strftime("%Y%m%d")
            elif start_date:
                date_str = start_date.strftime("%Y%m%d")
            else:
                date_str = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

            end_str = end_date.strftime("%Y%m%d") if end_date else date_str

            df = await self._run_with_retry(
                ak.stock_lhb_detail_em, start_date=date_str, end_date=end_str
            )

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["ts_code"] = df["代码"].apply(self._to_ts_code)
            result["trade_date"] = pd.to_datetime(df["上榜日期"], errors="coerce").dt.date
            result["reason"] = df.get("解读", "")
            result["buy_amount"] = pd.to_numeric(
                df.get("买入额", pd.Series(dtype=float)), errors="coerce"
            )
            result["sell_amount"] = pd.to_numeric(
                df.get("卖出额", pd.Series(dtype=float)), errors="coerce"
            )
            result["net_amount"] = pd.to_numeric(
                df.get("净买额", pd.Series(dtype=float)), errors="coerce"
            )
            result["broker_name"] = df.get("营业部名称", "")
            result["broker_type"] = "buy"

            logger.info("Fetched %d dragon-tiger entries", len(result))
            return result

        except Exception as exc:
            logger.error("Failed to fetch dragon-tiger from AKShare: %s", exc)
            raise DataProviderError(f"AKShare dragon-tiger fetch failed: {exc}") from exc

    async def fetch_northbound_flow(
        self,
        ts_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch northbound (Stock Connect) capital flow.

        - When ``ts_code`` is given, fetches individual stock flow via
          ``ak.stock_hsgt_individual_em``.
        - Otherwise fetches aggregate northbound net flow via
          ``ak.stock_hsgt_north_net_flow_in_em``.
        """
        import akshare as ak

        try:
            if ts_code:
                symbol = ts_code.split(".")[0]
                df = await self._run_with_retry(ak.stock_hsgt_individual_em, symbol=symbol)
            else:
                df = await self._run_with_retry(
                    ak.stock_hsgt_north_net_flow_in_em, symbol="北上"
                )

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            if ts_code:
                result["ts_code"] = ts_code
                result["trade_date"] = pd.to_datetime(
                    df.get("日期", df.iloc[:, 0]), errors="coerce"
                ).dt.date
                result["channel"] = "sh" if ts_code.endswith(".SH") else "sz"
                result["net_amount"] = pd.to_numeric(
                    df.get("当日净流入", df.iloc[:, 1]), errors="coerce"
                )
            else:
                result["ts_code"] = None
                result["trade_date"] = pd.to_datetime(
                    df.get("日期", df.iloc[:, 0]), errors="coerce"
                ).dt.date
                result["channel"] = "all"
                result["net_amount"] = pd.to_numeric(
                    df.get("当日净流入", df.iloc[:, 1]), errors="coerce"
                )

            result["buy_amount"] = None
            result["sell_amount"] = None
            result["hold_volume"] = None
            result["hold_ratio"] = None

            logger.info("Fetched %d northbound flow records", len(result))
            return result

        except Exception as exc:
            logger.error("Failed to fetch northbound flow from AKShare: %s", exc)
            raise DataProviderError(f"AKShare northbound flow fetch failed: {exc}") from exc

    async def fetch_trading_calendar(
        self,
        exchange: str = "SSE",
        year: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch the trading calendar for a given exchange and year.

        Uses ``ak.tool_trade_date_hist_sina`` to obtain all historical
        trading dates, then generates a day-by-day calendar for the
        requested range marking each day as open or closed.
        """
        import akshare as ak

        try:
            df = await self._run_with_retry(ak.tool_trade_date_hist_sina)

            if df.empty:
                return pd.DataFrame()

            trade_dates = set(pd.to_datetime(df["trade_date"]).dt.date)

            yr = year or datetime.now().year
            sd = start_date or date(yr, 1, 1)
            ed = end_date or date(yr, 12, 31)

            all_dates = pd.date_range(sd, ed, freq="D")

            result = pd.DataFrame()
            result["cal_date"] = all_dates.date
            result["is_open"] = [d in trade_dates for d in all_dates.date]
            result["exchange"] = exchange
            result["pre_trade_date"] = None

            # Calculate previous trading date for each row
            prev = None
            pre_dates = []
            for _, row in result.iterrows():
                pre_dates.append(prev)
                if row["is_open"]:
                    prev = row["cal_date"]
            result["pre_trade_date"] = pre_dates

            logger.info(
                "Generated trading calendar for %d (%d trading days)",
                yr,
                result["is_open"].sum(),
            )
            return result

        except Exception as exc:
            logger.error("Failed to fetch trading calendar from AKShare: %s", exc)
            raise DataProviderError(f"AKShare trading calendar fetch failed: {exc}") from exc

    async def fetch_sector_classification(
        self,
        classification: str = "shenwan",
        level: int = 1,
    ) -> pd.DataFrame:
        """Fetch sector / industry classification list.

        Uses ``ak.stock_board_industry_name_em`` (EastMoney industry
        boards).  The ``classification`` and ``level`` parameters are
        accepted for interface compatibility but the underlying AKShare
        endpoint currently returns EastMoney's own classification.
        """
        import akshare as ak

        try:
            df = await self._run_with_retry(ak.stock_board_industry_name_em)

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["sector_code"] = df["板块代码"].astype(str)
            result["sector_name"] = df["板块名称"]
            result["level"] = level
            result["parent_code"] = None
            result["classification"] = "eastmoney"

            logger.info("Fetched %d sectors from AKShare", len(result))
            return result

        except Exception as exc:
            logger.error("Failed to fetch sector classification from AKShare: %s", exc)
            raise DataProviderError(
                f"AKShare sector classification fetch failed: {exc}"
            ) from exc

    async def fetch_stock_sector_map(
        self,
        classification: str = "shenwan",
    ) -> pd.DataFrame:
        """Fetch the mapping from stocks to sectors.

        Iterates over every sector returned by
        ``ak.stock_board_industry_name_em`` and fetches its constituents
        via ``ak.stock_board_industry_cons_em``.  Per-sector errors are
        logged as warnings and skipped so that a single failing sector
        does not abort the entire operation.
        """
        import akshare as ak

        try:
            sectors_df = await self._run_with_retry(ak.stock_board_industry_name_em)

            all_mappings: list[dict[str, Any]] = []
            for _, sector in sectors_df.iterrows():
                try:
                    sector_name = sector["板块名称"]
                    sector_code = str(sector["板块代码"])

                    cons_df = await self._run_with_retry(
                        ak.stock_board_industry_cons_em, symbol=sector_name
                    )

                    if not cons_df.empty:
                        for _, stock in cons_df.iterrows():
                            all_mappings.append(
                                {
                                    "ts_code": self._to_ts_code(stock["代码"]),
                                    "sector_code": sector_code,
                                    "classification": "eastmoney",
                                    "in_date": None,
                                    "out_date": None,
                                }
                            )
                except Exception as inner_exc:
                    logger.warning(
                        "Failed to fetch constituents for sector %s: %s",
                        sector.get("板块名称", "?"),
                        inner_exc,
                    )
                    continue

            result = pd.DataFrame(all_mappings)
            logger.info("Fetched %d stock-sector mappings", len(result))
            return result

        except Exception as exc:
            logger.error("Failed to fetch stock-sector map from AKShare: %s", exc)
            raise DataProviderError(f"AKShare stock-sector map fetch failed: {exc}") from exc

    async def fetch_daily_basic(
        self,
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Fetch daily basic indicators (PE, PB, market cap, turnover, etc.).

        Uses ``ak.stock_zh_a_spot_em`` which provides a real-time
        snapshot including valuation metrics for all A-shares.  When
        ``ts_code`` is provided the result is filtered to that stock.
        """
        import akshare as ak

        try:
            df = await self._run_with_retry(ak.stock_zh_a_spot_em)

            if df.empty:
                return pd.DataFrame()

            result = pd.DataFrame()
            result["ts_code"] = df["代码"].apply(self._to_ts_code)
            result["trade_date"] = trade_date or datetime.now().date()
            result["pe"] = pd.to_numeric(
                df.get("市盈率-动态", pd.Series(dtype=float)), errors="coerce"
            )
            result["pe_ttm"] = result["pe"]
            result["pb"] = pd.to_numeric(
                df.get("市净率", pd.Series(dtype=float)), errors="coerce"
            )
            result["total_mv"] = pd.to_numeric(
                df.get("总市值", pd.Series(dtype=float)), errors="coerce"
            )
            result["circ_mv"] = pd.to_numeric(
                df.get("流通市值", pd.Series(dtype=float)), errors="coerce"
            )
            result["turnover_rate"] = pd.to_numeric(
                df.get("换手率", pd.Series(dtype=float)), errors="coerce"
            )
            result["turnover_rate_f"] = result["turnover_rate"]
            result["volume_ratio"] = pd.to_numeric(
                df.get("量比", pd.Series(dtype=float)), errors="coerce"
            )

            if ts_code:
                result = result[result["ts_code"] == ts_code]

            logger.info("Fetched daily basic indicators for %d stocks", len(result))
            return result

        except Exception as exc:
            logger.error("Failed to fetch daily basic from AKShare: %s", exc)
            raise DataProviderError(f"AKShare daily basic fetch failed: {exc}") from exc
