"""Factor computation engine - orchestrates batch factor calculation."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from quant_os_domain_factor.services.registry import factor_registry
from quant_os_shared.errors import FactorComputeError

logger = logging.getLogger(__name__)


class FactorCalculator:
    """Engine for computing factor values from market data."""

    def compute_single(
        self,
        factor_name: str,
        ohlcv_data: pd.DataFrame,
        params: dict[str, Any] | None = None,
    ) -> pd.Series:
        """Compute a single factor for one stock's time series data."""
        if ohlcv_data.empty:
            raise FactorComputeError(f"Empty data for factor {factor_name}")
        try:
            result = factor_registry.compute(factor_name, ohlcv_data, params)
            result.name = factor_name
            return result
        except Exception as exc:
            raise FactorComputeError(
                f"Failed to compute factor {factor_name}: {exc}",
                code="FACTOR_COMPUTE_ERROR",
            ) from exc

    def compute_cross_section(
        self,
        factor_name: str,
        cross_section_data: dict[str, pd.DataFrame],
        trade_date: date,
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Compute factor values across multiple stocks for a single date."""
        results = []
        for ts_code, df in cross_section_data.items():
            try:
                series = self.compute_single(factor_name, df, params)
                if not series.empty:
                    series.index = pd.to_datetime(series.index)
                    target = pd.Timestamp(trade_date)
                    idx = series.index[series.index <= target]
                    if len(idx) > 0:
                        val = series.loc[idx[-1]]
                        if pd.notna(val) and np.isfinite(val):
                            results.append({
                                "ts_code": ts_code,
                                "trade_date": trade_date,
                                "value": float(val),
                            })
            except Exception as exc:
                logger.warning("Failed to compute %s for %s: %s", factor_name, ts_code, exc)
                continue

        if not results:
            return pd.DataFrame(columns=["ts_code", "trade_date", "value", "rank", "zscore"])

        result_df = pd.DataFrame(results)
        result_df["rank"] = result_df["value"].rank(pct=True)

        mean = result_df["value"].mean()
        std = result_df["value"].std()
        if std > 0:
            result_df["zscore"] = (result_df["value"] - mean) / std
        else:
            result_df["zscore"] = 0.0

        logger.info(
            "Cross-section factor %s computed for %d stocks on %s",
            factor_name, len(result_df), trade_date,
        )
        return result_df

    def compute_batch(
        self,
        factor_names: list[str],
        stock_data: dict[str, pd.DataFrame],
        trade_dates: list[date],
        params: dict[str, Any] | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Compute multiple factors across stocks and dates.

        Returns:
            Dict of {factor_name: DataFrame with cross-sectional results}
        """
        results: dict[str, pd.DataFrame] = {}

        for factor_name in factor_names:
            all_dates_results = []
            for td in trade_dates:
                cs_df = self.compute_cross_section(factor_name, stock_data, td, params)
                if not cs_df.empty:
                    all_dates_results.append(cs_df)

            if all_dates_results:
                results[factor_name] = pd.concat(all_dates_results, ignore_index=True)
                logger.info(
                    "Batch compute %s: %d total records across %d dates",
                    factor_name, len(results[factor_name]), len(trade_dates),
                )
            else:
                results[factor_name] = pd.DataFrame()

        return results

    @staticmethod
    def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
        """Winsorize extreme values."""
        lo = series.quantile(lower)
        hi = series.quantile(upper)
        return series.clip(lo, hi)

    @staticmethod
    def neutralize(
        factor_values: pd.Series,
        groups: pd.Series,
    ) -> pd.Series:
        """Neutralize factor by group (industry/size).

        Removes group mean from factor values.
        """
        df = pd.DataFrame({"factor": factor_values, "group": groups})
        group_means = df.groupby("group")["factor"].transform("mean")
        return factor_values - group_means
