"""Liquidity and price-volume factors."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quant_os_domain_factor.entities.factor import FactorCategory, FactorDirection
from quant_os_domain_factor.services.registry import register_factor


def _rolling_corr(left: pd.Series, right: pd.Series, period: int) -> pd.Series:
    return left.rolling(window=period).corr(right)


@register_factor(
    "amihud_illiquidity",
    category=FactorCategory.TECHNICAL,
    display_name="Amihud Illiquidity",
    description="Rolling mean of absolute return divided by traded amount",
    direction=FactorDirection.SHORT,
    params={"period": 20},
)
def compute_amihud_illiquidity(data: pd.DataFrame, params: dict) -> pd.Series:
    period = params.get("period", 20)

    returns = data.groupby("ts_code")["close"].pct_change().abs()
    amount = data["amount"] if "amount" in data else data["close"] * data["volume"]
    raw = returns / amount.replace(0, np.nan)
    return raw.groupby(data["ts_code"]).rolling(window=period).mean().reset_index(level=0, drop=True)


@register_factor(
    "price_volume_corr",
    category=FactorCategory.TECHNICAL,
    display_name="Price Volume Correlation",
    description="Rolling correlation between returns and volume changes",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_price_volume_corr(data: pd.DataFrame, params: dict) -> pd.Series:
    period = params.get("period", 20)

    returns = data.groupby("ts_code")["close"].pct_change()
    volume_change = data.groupby("ts_code")["volume"].pct_change()
    return (
        returns.groupby(data["ts_code"])
        .rolling(window=period)
        .corr(volume_change)
        .reset_index(level=0, drop=True)
    )


@register_factor(
    "turnover_stability",
    category=FactorCategory.TECHNICAL,
    display_name="Turnover Stability",
    description="Negative rolling volatility of turnover or volume",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_turnover_stability(data: pd.DataFrame, params: dict) -> pd.Series:
    period = params.get("period", 20)
    base = data["turnover_rate"] if "turnover_rate" in data else data.groupby("ts_code")["volume"].pct_change()
    return -base.groupby(data["ts_code"]).rolling(window=period).std().reset_index(level=0, drop=True)


@register_factor(
    "intraday_strength",
    category=FactorCategory.TECHNICAL,
    display_name="Intraday Strength",
    description="Close location in the daily high-low range",
    direction=FactorDirection.LONG,
    params={"period": 10},
)
def compute_intraday_strength(data: pd.DataFrame, params: dict) -> pd.Series:
    period = params.get("period", 10)
    spread = (data["high"] - data["low"]).replace(0, np.nan)
    raw = (data["close"] - data["low"]) / spread
    return raw.groupby(data["ts_code"]).rolling(window=period).mean().reset_index(level=0, drop=True)


@register_factor(
    "gap_reversal",
    category=FactorCategory.TECHNICAL,
    display_name="Gap Reversal",
    description="Negative overnight gap adjusted by intraday return",
    direction=FactorDirection.LONG,
    params={"period": 5},
)
def compute_gap_reversal(data: pd.DataFrame, params: dict) -> pd.Series:
    period = params.get("period", 5)

    def _calc(group: pd.DataFrame) -> pd.Series:
        previous_close = group["close"].shift(1)
        overnight_gap = group["open"] / previous_close - 1
        intraday_return = group["close"] / group["open"] - 1
        return (-overnight_gap + intraday_return).rolling(window=period).mean()

    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "breakout_strength",
    category=FactorCategory.TECHNICAL,
    display_name="Breakout Strength",
    description="Close price relative to recent high-low channel",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_breakout_strength(data: pd.DataFrame, params: dict) -> pd.Series:
    period = params.get("period", 20)

    def _calc(group: pd.DataFrame) -> pd.Series:
        high = group["high"].rolling(window=period).max()
        low = group["low"].rolling(window=period).min()
        return (group["close"] - low) / (high - low).replace(0, np.nan)

    return data.groupby("ts_code", group_keys=False).apply(_calc)
