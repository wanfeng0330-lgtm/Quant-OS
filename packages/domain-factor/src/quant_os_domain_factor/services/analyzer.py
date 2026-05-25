"""Factor analysis: IC, RankIC, and layered quantile backtest."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ICResult:
    """Result of IC (Information Coefficient) analysis."""
    factor_name: str
    start_date: date
    end_date: date
    ic_series: list[float] = field(default_factory=list)
    rank_ic_series: list[float] = field(default_factory=list)
    ic_dates: list[date] = field(default_factory=list)

    @property
    def ic_mean(self) -> float:
        return float(np.mean(self.ic_series)) if self.ic_series else 0.0

    @property
    def ic_std(self) -> float:
        return float(np.std(self.ic_series)) if self.ic_series else 0.0

    @property
    def icir(self) -> float:
        if self.ic_std > 0:
            return self.ic_mean / self.ic_std
        return 0.0

    @property
    def rank_ic_mean(self) -> float:
        return float(np.mean(self.rank_ic_series)) if self.rank_ic_series else 0.0

    @property
    def rank_ic_std(self) -> float:
        return float(np.std(self.rank_ic_series)) if self.rank_ic_series else 0.0

    @property
    def rank_icir(self) -> float:
        if self.rank_ic_std > 0:
            return self.rank_ic_mean / self.rank_ic_std
        return 0.0

    @property
    def ic_positive_ratio(self) -> float:
        if not self.ic_series:
            return 0.0
        return sum(1 for x in self.ic_series if x > 0) / len(self.ic_series)

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "start_date": str(self.start_date),
            "end_date": str(self.end_date),
            "ic_mean": round(self.ic_mean, 6),
            "ic_std": round(self.ic_std, 6),
            "icir": round(self.icir, 4),
            "rank_ic_mean": round(self.rank_ic_mean, 6),
            "rank_ic_std": round(self.rank_ic_std, 6),
            "rank_icir": round(self.rank_icir, 4),
            "ic_positive_ratio": round(self.ic_positive_ratio, 4),
            "periods": len(self.ic_series),
        }


@dataclass
class LayeredBacktestResult:
    """Result of layered (quantile) backtest."""
    factor_name: str
    start_date: date
    end_date: date
    n_groups: int = 5
    group_returns: dict[int, list[float]] = field(default_factory=dict)
    group_dates: list[date] = field(default_factory=list)
    long_short_returns: list[float] = field(default_factory=list)

    @property
    def group_annual_returns(self) -> dict[int, float]:
        result = {}
        for g, rets in self.group_returns.items():
            if rets:
                total = np.prod([1 + r for r in rets]) - 1
                n_years = max(len(rets) / 252, 0.01)
                result[g] = float((1 + total) ** (1 / n_years) - 1)
            else:
                result[g] = 0.0
        return result

    @property
    def long_short_sharpe(self) -> float:
        if not self.long_short_returns:
            return 0.0
        mean = np.mean(self.long_short_returns)
        std = np.std(self.long_short_returns)
        if std > 0:
            return float(mean / std * np.sqrt(252))
        return 0.0

    @property
    def monotonicity(self) -> float:
        """Check if returns are monotonically decreasing from group 1 to group N.
        Returns 1.0 for perfect monotonicity, 0 for none.
        """
        annual = self.group_annual_returns
        if len(annual) < 2:
            return 0.0
        sorted_groups = sorted(annual.keys())
        diffs = [annual[sorted_groups[i]] - annual[sorted_groups[i+1]] for i in range(len(sorted_groups)-1)]
        positive = sum(1 for d in diffs if d > 0)
        return positive / len(diffs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "start_date": str(self.start_date),
            "end_date": str(self.end_date),
            "n_groups": self.n_groups,
            "group_annual_returns": {str(k): round(v, 6) for k, v in self.group_annual_returns.items()},
            "long_short_sharpe": round(self.long_short_sharpe, 4),
            "monotonicity": round(self.monotonicity, 4),
            "periods": len(self.group_dates),
        }


class FactorAnalyzer:
    """Performs IC analysis and layered backtests on factors."""

    def compute_ic(
        self,
        factor_values: pd.DataFrame,
        forward_returns: pd.DataFrame,
    ) -> ICResult:
        """Compute IC (Information Coefficient) between factor values and forward returns.

        Args:
            factor_values: DataFrame with columns [ts_code, trade_date, value]
            forward_returns: DataFrame with columns [ts_code, trade_date, return]

        Returns:
            ICResult with IC series and statistics
        """
        merged = pd.merge(
            factor_values, forward_returns,
            on=["ts_code", "trade_date"],
            how="inner",
        )

        if merged.empty:
            factor_name = factor_values.get("factor_name", pd.Series(["unknown"])).iloc[0] if "factor_name" in factor_values.columns else "unknown"
            return ICResult(factor_name=str(factor_name), start_date=date.today(), end_date=date.today())

        dates = sorted(merged["trade_date"].unique())
        ic_series = []
        rank_ic_series = []
        ic_dates = []

        for d in dates:
            day_data = merged[merged["trade_date"] == d]
            if len(day_data) < 10:
                continue

            factor_vals = day_data["value"]
            ret_vals = day_data["return"]

            # Pearson IC
            ic = factor_vals.corr(ret_vals)
            if pd.notna(ic):
                ic_series.append(ic)
                ic_dates.append(d)

            # Spearman Rank IC
            rank_ic = factor_vals.rank().corr(ret_vals.rank())
            if pd.notna(rank_ic):
                rank_ic_series.append(rank_ic)

        factor_name = "unknown"
        if "factor_name" in factor_values.columns and not factor_values.empty:
            factor_name = str(factor_values["factor_name"].iloc[0])

        result = ICResult(
            factor_name=factor_name,
            start_date=dates[0] if dates else date.today(),
            end_date=dates[-1] if dates else date.today(),
            ic_series=ic_series,
            rank_ic_series=rank_ic_series,
            ic_dates=ic_dates,
        )

        logger.info(
            "IC analysis for %s: IC=%.4f, RankIC=%.4f, ICIR=%.4f (%d periods)",
            result.factor_name, result.ic_mean, result.rank_ic_mean,
            result.icir, len(ic_series),
        )
        return result

    def compute_forward_returns(
        self,
        ohlcv_data: pd.DataFrame,
        periods: int = 5,
    ) -> pd.DataFrame:
        """Compute forward returns from OHLCV data.

        Args:
            ohlcv_data: DataFrame with columns [ts_code, trade_date, close]
            periods: Forward return period in trading days

        Returns:
            DataFrame with columns [ts_code, trade_date, return]
        """
        if ohlcv_data.empty:
            return pd.DataFrame(columns=["ts_code", "trade_date", "return"])

        result_frames = []
        for ts_code, group in ohlcv_data.groupby("ts_code"):
            group = group.sort_values("trade_date").copy()
            group["fwd_return"] = group["close"].shift(-periods) / group["close"] - 1
            group = group.dropna(subset=["fwd_return"])

            frame = pd.DataFrame({
                "ts_code": ts_code,
                "trade_date": group["trade_date"],
                "return": group["fwd_return"],
            })
            result_frames.append(frame)

        if not result_frames:
            return pd.DataFrame(columns=["ts_code", "trade_date", "return"])

        return pd.concat(result_frames, ignore_index=True)

    def layered_backtest(
        self,
        factor_values: pd.DataFrame,
        forward_returns: pd.DataFrame,
        n_groups: int = 5,
    ) -> LayeredBacktestResult:
        """Run layered (quantile) backtest.

        Sorts stocks by factor value into N groups each period,
        then computes group returns.

        Args:
            factor_values: DataFrame with columns [ts_code, trade_date, value]
            forward_returns: DataFrame with columns [ts_code, trade_date, return]
            n_groups: Number of quantile groups (default 5)
        """
        merged = pd.merge(
            factor_values, forward_returns,
            on=["ts_code", "trade_date"],
            how="inner",
        )

        if merged.empty:
            factor_name = "unknown"
            return LayeredBacktestResult(
                factor_name=factor_name,
                start_date=date.today(),
                end_date=date.today(),
                n_groups=n_groups,
            )

        dates = sorted(merged["trade_date"].unique())
        group_returns: dict[int, list[float]] = {i: [] for i in range(1, n_groups + 1)}
        long_short_returns = []
        group_dates = []

        for d in dates:
            day_data = merged[merged["trade_date"] == d].copy()
            if len(day_data) < n_groups * 5:
                continue

            day_data["group"] = pd.qcut(
                day_data["value"], n_groups,
                labels=range(1, n_groups + 1),
                duplicates="drop",
            )

            for g in range(1, n_groups + 1):
                g_data = day_data[day_data["group"] == g]
                if not g_data.empty:
                    group_returns[g].append(float(g_data["return"].mean()))

            # Long-short: group 1 (top) minus group N (bottom)
            top_ret = day_data[day_data["group"] == 1]["return"].mean()
            bottom_ret = day_data[day_data["group"] == n_groups]["return"].mean()
            if pd.notna(top_ret) and pd.notna(bottom_ret):
                long_short_returns.append(float(top_ret - bottom_ret))

            group_dates.append(d)

        factor_name = "unknown"
        if "factor_name" in factor_values.columns and not factor_values.empty:
            factor_name = str(factor_values["factor_name"].iloc[0])

        result = LayeredBacktestResult(
            factor_name=factor_name,
            start_date=dates[0] if dates else date.today(),
            end_date=dates[-1] if dates else date.today(),
            n_groups=n_groups,
            group_returns=group_returns,
            group_dates=group_dates,
            long_short_returns=long_short_returns,
        )

        logger.info(
            "Layered backtest for %s: %d groups, %d periods, L/S Sharpe=%.4f",
            result.factor_name, n_groups, len(group_dates), result.long_short_sharpe,
        )
        return result
