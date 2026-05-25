"""Technical indicators and factors.

This module implements common technical analysis factors including:
- Momentum factors (ROC, MOM, RSI, etc.)
- Moving average factors (MA, EMA, MACD, etc.)
- Volatility factors (ATR, Std, Bollinger Bands, etc.)
- Volume factors (OBV, Volume Ratio, VWAP, etc.)
- Oscillator factors (KDJ, CCI, Williams %R, etc.)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quant_os_domain_factor.entities.factor import FactorCategory, FactorDirection
from quant_os_domain_factor.services.registry import register_factor


# =============================================================================
# Helper Functions
# =============================================================================

def _ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return series.rolling(window=period).mean()


def _std(series: pd.Series, period: int) -> pd.Series:
    """Calculate Rolling Standard Deviation."""
    return series.rolling(window=period).std()


def _max(series: pd.Series, period: int) -> pd.Series:
    """Calculate Rolling Max."""
    return series.rolling(window=period).max()


def _min(series: pd.Series, period: int) -> pd.Series:
    """Calculate Rolling Min."""
    return series.rolling(window=period).min()


def _sum(series: pd.Series, period: int) -> pd.Series:
    """Calculate Rolling Sum."""
    return series.rolling(window=period).sum()


def _corr(x: pd.Series, y: pd.Series, period: int) -> pd.Series:
    """Calculate Rolling Correlation."""
    return x.rolling(window=period).corr(y)


def _rank(series: pd.Series) -> pd.Series:
    """Calculate Cross-sectional Rank (percentile)."""
    return series.rank(pct=True)


def _delta(series: pd.Series, period: int = 1) -> pd.Series:
    """Calculate Difference."""
    return series.diff(period)


def _delay(series: pd.Series, period: int = 1) -> pd.Series:
    """Calculate Delay (shift)."""
    return series.shift(period)


def _ts_argmax(series: pd.Series, period: int) -> pd.Series:
    """Calculate Time-series ArgMax (position of max value)."""
    return series.rolling(window=period).apply(lambda x: np.argmax(x) + 1, raw=True)


def _ts_argmin(series: pd.Series, period: int) -> pd.Series:
    """Calculate Time-series ArgMin (position of min value)."""
    return series.rolling(window=period).apply(lambda x: np.argmin(x) + 1, raw=True)


# =============================================================================
# Momentum Factors
# =============================================================================

@register_factor(
    "momentum",
    category=FactorCategory.TECHNICAL,
    description="Price momentum (rate of change)",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_momentum(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate price momentum factor.
    
    Formula: close / close.shift(period) - 1
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"period": int}
    
    Returns:
        Series with momentum values
    """
    period = params.get("period", 20)
    return data.groupby("ts_code")["close"].pct_change(periods=period)


@register_factor(
    "roc",
    category=FactorCategory.TECHNICAL,
    description="Rate of Change",
    direction=FactorDirection.LONG,
    params={"period": 12},
)
def compute_roc(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate Rate of Change factor.
    
    Formula: (close - close.shift(period)) / close.shift(period) * 100
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"period": int}
    
    Returns:
        Series with ROC values
    """
    period = params.get("period", 12)
    prev_close = data.groupby("ts_code")["close"].shift(period)
    return (data["close"] - prev_close) / prev_close * 100


@register_factor(
    "rsi",
    category=FactorCategory.TECHNICAL,
    description="Relative Strength Index",
    direction=FactorDirection.LONG,
    params={"period": 14},
)
def compute_rsi(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate Relative Strength Index.
    
    Formula: 100 - 100 / (1 + avg_gain / avg_loss)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"period": int}
    
    Returns:
        Series with RSI values (0-100)
    """
    period = params.get("period", 14)
    
    def _calc_rsi(group):
        delta = group["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_rsi)


@register_factor(
    "momentum_20",
    category=FactorCategory.TECHNICAL,
    description="20-day price momentum",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_momentum_20(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate 20-day momentum factor (alias for momentum)."""
    return compute_momentum(data, {"period": 20})


@register_factor(
    "momentum_60",
    category=FactorCategory.TECHNICAL,
    description="60-day price momentum",
    direction=FactorDirection.LONG,
    params={"period": 60},
)
def compute_momentum_60(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate 60-day momentum factor."""
    return compute_momentum(data, {"period": 60})


@register_factor(
    "momentum_120",
    category=FactorCategory.TECHNICAL,
    description="120-day price momentum",
    direction=FactorDirection.LONG,
    params={"period": 120},
)
def compute_momentum_120(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate 120-day momentum factor."""
    return compute_momentum(data, {"period": 120})


@register_factor(
    "relative_strength",
    category=FactorCategory.TECHNICAL,
    description="Relative strength vs market",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_relative_strength(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate relative strength factor.
    
    Formula: stock_return / market_return over period
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"period": int}
    
    Returns:
        Series with relative strength values
    """
    period = params.get("period", 20)
    
    # Calculate stock returns
    stock_returns = data.groupby("ts_code")["close"].pct_change(periods=period)
    
    # Calculate market returns (equal-weighted average)
    daily_returns = data.groupby("ts_code")["close"].pct_change()
    market_returns = daily_returns.groupby(data["trade_date"]).transform("mean")
    market_cumulative = (1 + market_returns).groupby(data["trade_date"]).cumprod() - 1
    
    return stock_returns / market_cumulative.replace(0, np.nan)


# =============================================================================
# Moving Average Factors
# =============================================================================

@register_factor(
    "ma_cross",
    category=FactorCategory.TECHNICAL,
    description="Moving average crossover signal",
    direction=FactorDirection.LONG,
    params={"short_period": 5, "long_period": 20},
)
def compute_ma_cross(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate moving average crossover factor.
    
    Formula: MA(short) / MA(long) - 1
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"short_period": int, "long_period": int}
    
    Returns:
        Series with MA cross values (positive = bullish)
    """
    short_period = params.get("short_period", 5)
    long_period = params.get("long_period", 20)
    
    def _calc_ma_cross(group):
        ma_short = _sma(group["close"], short_period)
        ma_long = _sma(group["close"], long_period)
        return ma_short / ma_long - 1
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_ma_cross)


@register_factor(
    "ema_bias",
    category=FactorCategory.TECHNICAL,
    description="EMA bias ratio",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_ema_bias(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate EMA bias factor.
    
    Formula: (close - EMA(period)) / EMA(period)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"period": int}
    
    Returns:
        Series with EMA bias values
    """
    period = params.get("period", 20)
    
    def _calc_ema_bias(group):
        ema = _ema(group["close"], period)
        return (group["close"] - ema) / ema
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_ema_bias)


@register_factor(
    "macd",
    category=FactorCategory.TECHNICAL,
    description="MACD histogram",
    direction=FactorDirection.LONG,
    params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
)
def compute_macd(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate MACD histogram factor.
    
    Formula: MACD Line - Signal Line
    where MACD Line = EMA(fast) - EMA(slow)
          Signal Line = EMA(MACD Line, signal_period)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"fast_period": int, "slow_period": int, "signal_period": int}
    
    Returns:
        Series with MACD histogram values
    """
    fast_period = params.get("fast_period", 12)
    slow_period = params.get("slow_period", 26)
    signal_period = params.get("signal_period", 9)
    
    def _calc_macd(group):
        ema_fast = _ema(group["close"], fast_period)
        ema_slow = _ema(group["close"], slow_period)
        macd_line = ema_fast - ema_slow
        signal_line = _ema(macd_line, signal_period)
        return macd_line - signal_line
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_macd)


# =============================================================================
# Volatility Factors
# =============================================================================

@register_factor(
    "volatility",
    category=FactorCategory.TECHNICAL,
    description="Price volatility (rolling std)",
    direction=FactorDirection.SHORT,
    params={"period": 20},
)
def compute_volatility(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate price volatility factor.
    
    Formula: rolling standard deviation of daily returns
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"period": int}
    
    Returns:
        Series with volatility values
    """
    period = params.get("period", 20)
    
    def _calc_vol(group):
        returns = group["close"].pct_change()
        return _std(returns, period)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_vol)


@register_factor(
    "atr",
    category=FactorCategory.TECHNICAL,
    description="Average True Range",
    direction=FactorDirection.SHORT,
    params={"period": 14},
)
def compute_atr(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate Average True Range factor.
    
    Formula: EMA of True Range
    where True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, high, low, close]
        params: {"period": int}
    
    Returns:
        Series with ATR values
    """
    period = params.get("period", 14)
    
    def _calc_atr(group):
        high = group["high"]
        low = group["low"]
        prev_close = group["close"].shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return _ema(true_range, period)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_atr)


@register_factor(
    "bollinger_width",
    category=FactorCategory.TECHNICAL,
    description="Bollinger Band Width",
    direction=FactorDirection.SHORT,
    params={"period": 20, "num_std": 2},
)
def compute_bollinger_width(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate Bollinger Band Width factor.
    
    Formula: (Upper Band - Lower Band) / Middle Band
    where Middle Band = SMA(period)
          Upper Band = Middle Band + num_std * Std(period)
          Lower Band = Middle Band - num_std * Std(period)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"period": int, "num_std": float}
    
    Returns:
        Series with Bollinger Band Width values
    """
    period = params.get("period", 20)
    num_std = params.get("num_std", 2)
    
    def _calc_bollinger(group):
        middle = _sma(group["close"], period)
        std = _std(group["close"], period)
        upper = middle + num_std * std
        lower = middle - num_std * std
        return (upper - lower) / middle
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_bollinger)


@register_factor(
    "downside_volatility",
    category=FactorCategory.TECHNICAL,
    description="Downside volatility (semi-deviation)",
    direction=FactorDirection.SHORT,
    params={"period": 20},
)
def compute_downside_volatility(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate downside volatility factor.
    
    Formula: rolling standard deviation of negative daily returns
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"period": int}
    
    Returns:
        Series with downside volatility values
    """
    period = params.get("period", 20)
    
    def _calc_downside_vol(group):
        returns = group["close"].pct_change()
        negative_returns = returns.where(returns < 0, 0.0)
        return _std(negative_returns, period)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_downside_vol)


# =============================================================================
# Volume Factors
# =============================================================================

@register_factor(
    "volume_ratio",
    category=FactorCategory.TECHNICAL,
    description="Volume ratio (current vs average)",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_volume_ratio(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate volume ratio factor.
    
    Formula: volume / SMA(volume, period)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, volume]
        params: {"period": int}
    
    Returns:
        Series with volume ratio values
    """
    period = params.get("period", 20)
    
    def _calc_vol_ratio(group):
        avg_vol = _sma(group["volume"], period)
        return group["volume"] / avg_vol.replace(0, np.nan)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_vol_ratio)


@register_factor(
    "obv",
    category=FactorCategory.TECHNICAL,
    description="On-Balance Volume",
    direction=FactorDirection.LONG,
    params={},
)
def compute_obv(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate On-Balance Volume factor.
    
    Formula: cumulative sum of (sign(close_change) * volume)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, volume]
        params: {}
    
    Returns:
        Series with OBV values (normalized)
    """
    def _calc_obv(group):
        close_change = group["close"].diff()
        obv = (np.sign(close_change) * group["volume"]).cumsum()
        # Normalize by rolling window
        return obv / _sma(obv.abs(), 20).replace(0, np.nan)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_obv)


@register_factor(
    "volume_momentum",
    category=FactorCategory.TECHNICAL,
    description="Volume momentum",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_volume_momentum(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate volume momentum factor.
    
    Formula: volume / volume.shift(period) - 1
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, volume]
        params: {"period": int}
    
    Returns:
        Series with volume momentum values
    """
    period = params.get("period", 20)
    return data.groupby("ts_code")["volume"].pct_change(periods=period)


@register_factor(
    "vwap_bias",
    category=FactorCategory.TECHNICAL,
    description="VWAP bias",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_vwap_bias(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate VWAP bias factor.
    
    Formula: close / VWAP - 1
    where VWAP = sum(amount) / sum(volume) over period
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, amount, volume]
        params: {"period": int}
    
    Returns:
        Series with VWAP bias values
    """
    period = params.get("period", 20)
    
    def _calc_vwap_bias(group):
        if "amount" in group.columns:
            vwap = _sum(group["amount"], period) / _sum(group["volume"], period)
        else:
            # Fallback: use typical price * volume
            typical_price = (group["high"] + group["low"] + group["close"]) / 3
            vwap = _sum(typical_price * group["volume"], period) / _sum(group["volume"], period)
        return group["close"] / vwap - 1
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_vwap_bias)


# =============================================================================
# Oscillator Factors
# =============================================================================

@register_factor(
    "cci",
    category=FactorCategory.TECHNICAL,
    description="Commodity Channel Index",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_cci(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate Commodity Channel Index factor.
    
    Formula: (Typical Price - SMA(Typical Price)) / (0.015 * Mean Deviation)
    where Typical Price = (high + low + close) / 3
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, high, low, close]
        params: {"period": int}
    
    Returns:
        Series with CCI values
    """
    period = params.get("period", 20)
    
    def _calc_cci(group):
        tp = (group["high"] + group["low"] + group["close"]) / 3
        sma_tp = _sma(tp, period)
        mad = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
        return (tp - sma_tp) / (0.015 * mad)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_cci)


@register_factor(
    "williams_r",
    category=FactorCategory.TECHNICAL,
    description="Williams %R",
    direction=FactorDirection.LONG,
    params={"period": 14},
)
def compute_williams_r(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate Williams %R factor.
    
    Formula: (Highest High - Close) / (Highest High - Lowest Low) * -100
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, high, low, close]
        params: {"period": int}
    
    Returns:
        Series with Williams %R values (-100 to 0)
    """
    period = params.get("period", 14)
    
    def _calc_williams(group):
        highest_high = _max(group["high"], period)
        lowest_low = _min(group["low"], period)
        return (highest_high - group["close"]) / (highest_high - lowest_low) * -100
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_williams)


@register_factor(
    "stoch_k",
    category=FactorCategory.TECHNICAL,
    description="Stochastic Oscillator %K",
    direction=FactorDirection.LONG,
    params={"period": 14},
)
def compute_stoch_k(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate Stochastic Oscillator %K factor.
    
    Formula: (Close - Lowest Low) / (Highest High - Lowest Low) * 100
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, high, low, close]
        params: {"period": int}
    
    Returns:
        Series with %K values (0-100)
    """
    period = params.get("period", 14)
    
    def _calc_stoch(group):
        highest_high = _max(group["high"], period)
        lowest_low = _min(group["low"], period)
        return (group["close"] - lowest_low) / (highest_high - lowest_low) * 100
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_stoch)


# =============================================================================
# Pattern Factors
# =============================================================================

@register_factor(
    "price_range",
    category=FactorCategory.TECHNICAL,
    description="Price range ratio",
    direction=FactorDirection.SHORT,
    params={"period": 20},
)
def compute_price_range(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate price range factor.
    
    Formula: (Highest High - Lowest Low) / Close over period
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, high, low, close]
        params: {"period": int}
    
    Returns:
        Series with price range values
    """
    period = params.get("period", 20)
    
    def _calc_range(group):
        highest_high = _max(group["high"], period)
        lowest_low = _min(group["low"], period)
        return (highest_high - lowest_low) / group["close"]
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_range)


@register_factor(
    "close_to_high",
    category=FactorCategory.TECHNICAL,
    description="Close position relative to high",
    direction=FactorDirection.LONG,
    params={"period": 20},
)
def compute_close_to_high(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate close-to-high ratio factor.
    
    Formula: (Close - Lowest Low) / (Highest High - Lowest Low)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, high, low, close]
        params: {"period": int}
    
    Returns:
        Series with close-to-high values (0-1)
    """
    period = params.get("period", 20)
    
    def _calc_close_high(group):
        highest_high = _max(group["high"], period)
        lowest_low = _min(group["low"], period)
        return (group["close"] - lowest_low) / (highest_high - lowest_low)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_close_high)


@register_factor(
    "mean_reversion",
    category=FactorCategory.TECHNICAL,
    description="Mean reversion signal",
    direction=FactorDirection.SHORT,
    params={"period": 20},
)
def compute_mean_reversion(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate mean reversion factor.
    
    Formula: -(close / SMA(period) - 1)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"period": int}
    
    Returns:
        Series with mean reversion values (negative = overbought)
    """
    period = params.get("period", 20)
    
    def _calc_mean_rev(group):
        sma = _sma(group["close"], period)
        return -(group["close"] / sma - 1)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_mean_rev)


# =============================================================================
# Composite Factors
# =============================================================================

@register_factor(
    "quality_momentum",
    category=FactorCategory.TECHNICAL,
    description="Quality-adjusted momentum",
    direction=FactorDirection.LONG,
    params={"momentum_period": 60, "vol_period": 20},
)
def compute_quality_momentum(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate quality-adjusted momentum factor.
    
    Formula: momentum / volatility
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"momentum_period": int, "vol_period": int}
    
    Returns:
        Series with quality momentum values
    """
    momentum_period = params.get("momentum_period", 60)
    vol_period = params.get("vol_period", 20)
    
    mom = compute_momentum(data, {"period": momentum_period})
    vol = compute_volatility(data, {"period": vol_period})
    
    return mom / vol.replace(0, np.nan)


@register_factor(
    "risk_adjusted_momentum",
    category=FactorCategory.TECHNICAL,
    description="Risk-adjusted momentum (Sharpe-like)",
    direction=FactorDirection.LONG,
    params={"period": 60},
)
def compute_risk_adjusted_momentum(data: pd.DataFrame, params: dict) -> pd.Series:
    """Calculate risk-adjusted momentum factor.
    
    Formula: mean(returns) / std(returns) over period
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
        params: {"period": int}
    
    Returns:
        Series with risk-adjusted momentum values
    """
    period = params.get("period", 60)
    
    def _calc_risk_adj(group):
        returns = group["close"].pct_change()
        mean_ret = returns.rolling(window=period).mean()
        std_ret = returns.rolling(window=period).std()
        return mean_ret / std_ret.replace(0, np.nan) * np.sqrt(252)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc_risk_adj)
