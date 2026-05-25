"""WorldQuant Alpha101 Factors.

This module implements selected factors from the WorldQuant 101 Alphas paper.
Reference: Kakushadze, Z. (2016). 101 Formulaic Alphas. Wilmott, 2016(84), 72-81.

Note: Many Alpha101 factors require cross-sectional operations (rank, etc.)
which are computed using pandas rank with pct=True for percentile ranking.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quant_os_domain_factor.entities.factor import FactorCategory, FactorDirection
from quant_os_domain_factor.services.registry import register_factor


# =============================================================================
# Helper Functions
# =============================================================================

def _rank(series: pd.Series) -> pd.Series:
    """Cross-sectional rank (percentile)."""
    return series.rank(pct=True)


def _delta(series: pd.Series, period: int = 1) -> pd.Series:
    """Time-series difference."""
    return series.diff(period)


def _delay(series: pd.Series, period: int = 1) -> pd.Series:
    """Time-series delay (shift)."""
    return series.shift(period)


def _correlation(x: pd.Series, y: pd.Series, period: int) -> pd.Series:
    """Rolling correlation."""
    return x.rolling(window=period).corr(y)


def _covariance(x: pd.Series, y: pd.Series, period: int) -> pd.Series:
    """Rolling covariance."""
    return x.rolling(window=period).cov(y)


def _ts_min(series: pd.Series, period: int) -> pd.Series:
    """Rolling min."""
    return series.rolling(window=period).min()


def _ts_max(series: pd.Series, period: int) -> pd.Series:
    """Rolling max."""
    return series.rolling(window=period).max()


def _ts_argmin(series: pd.Series, period: int) -> pd.Series:
    """Position of min in rolling window."""
    return series.rolling(window=period).apply(lambda x: np.argmin(x) + 1, raw=True)


def _ts_argmax(series: pd.Series, period: int) -> pd.Series:
    """Position of max in rolling window."""
    return series.rolling(window=period).apply(lambda x: np.argmax(x) + 1, raw=True)


def _sum(series: pd.Series, period: int) -> pd.Series:
    """Rolling sum."""
    return series.rolling(window=period).sum()


def _std(series: pd.Series, period: int) -> pd.Series:
    """Rolling standard deviation."""
    return series.rolling(window=period).std()


def _sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window=period).mean()


def _product(series: pd.Series, period: int) -> pd.Series:
    """Rolling product."""
    return series.rolling(window=period).apply(lambda x: np.prod(x), raw=True)


def _sign(series: pd.Series) -> pd.Series:
    """Sign function."""
    return np.sign(series)


def _log(series: pd.Series) -> pd.Series:
    """Natural logarithm."""
    return np.log(series.replace(0, np.nan))


def _abs(series: pd.Series) -> pd.Series:
    """Absolute value."""
    return series.abs()


def _signed_power(series: pd.Series, exp: float) -> pd.Series:
    """Signed power: sign(x) * |x|^exp."""
    return np.sign(series) * np.abs(series) ** exp


def _decay_linear(series: pd.Series, period: int) -> pd.Series:
    """Linear decay weighted average."""
    weights = np.arange(1, period + 1, dtype=float)
    weights = weights / weights.sum()
    return series.rolling(window=period).apply(lambda x: np.dot(x, weights), raw=True)


# =============================================================================
# Alpha101 Factors
# =============================================================================

@register_factor(
    "alpha001",
    category=FactorCategory.ALPHA101,
    description="Alpha#001: (rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha001(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#001.
    
    Formula: (rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        close = group["close"]
        returns = close.pct_change()
        std_ret = _std(returns, 20)
        
        # Conditional: returns < 0 ? std(returns, 20) : close
        cond_value = pd.Series(np.where(returns < 0, std_ret, close), index=close.index)
        
        # SignedPower(x, 2)
        signed_power = _signed_power(cond_value, 2.0)
        
        # Ts_ArgMax over 5 days
        argmax = _ts_argmax(signed_power, 5)
        
        return argmax
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return _rank(result) - 0.5


@register_factor(
    "alpha002",
    category=FactorCategory.ALPHA101,
    description="Alpha#002: -1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6)",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha002(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#002.
    
    Formula: -1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, open, volume]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        volume = group["volume"]
        close = group["close"]
        open_price = group["open"]
        
        # rank(delta(log(volume), 2))
        delta_log_vol = _delta(_log(volume), 2)
        rank_delta_log_vol = _rank(delta_log_vol)
        
        # rank(((close - open) / open))
        intra_return = (close - open_price) / open_price
        rank_intra_return = _rank(intra_return)
        
        # correlation(..., 6)
        corr = _correlation(rank_delta_log_vol, rank_intra_return, 6)
        
        return corr
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return -1 * result


@register_factor(
    "alpha006",
    category=FactorCategory.ALPHA101,
    description="Alpha#006: -1 * correlation(open, volume, 10)",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha006(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#006.
    
    Formula: -1 * correlation(open, volume, 10)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, open, volume]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        return _correlation(group["open"], group["volume"], 10)
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return -1 * result


@register_factor(
    "alpha012",
    category=FactorCategory.ALPHA101,
    description="Alpha#012: sign(delta(volume, 1)) * (-1 * delta(close, 1))",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha012(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#012.
    
    Formula: sign(delta(volume, 1)) * (-1 * delta(close, 1))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, volume]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        sign_vol = _sign(_delta(group["volume"], 1))
        delta_close = -1 * _delta(group["close"], 1)
        return sign_vol * delta_close
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "alpha020",
    category=FactorCategory.ALPHA101,
    description="Alpha#020: (rank(open - delay(high, 1))) * (rank(open - delay(close, 1))) * (rank(open - delay(low, 1)))",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha020(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#020.
    
    Formula: (rank(open - delay(high, 1))) * (rank(open - delay(close, 1))) * (rank(open - delay(low, 1)))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, open, high, low, close]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        open_price = group["open"]
        high = group["high"]
        low = group["low"]
        close = group["close"]
        
        r1 = _rank(open_price - _delay(high, 1))
        r2 = _rank(open_price - _delay(close, 1))
        r3 = _rank(open_price - _delay(low, 1))
        
        return r1 * r2 * r3
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "alpha026",
    category=FactorCategory.ALPHA101,
    description="Alpha#026: -1 * ts_max(correlation(ts_rank(volume, 5), ts_rank(high, 5), 5), 3)",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha026(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#026.
    
    Formula: -1 * ts_max(correlation(ts_rank(volume, 5), ts_rank(high, 5), 5), 3)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, volume, high]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        volume = group["volume"]
        high = group["high"]
        
        # ts_rank over 5 days
        ts_rank_vol = volume.rolling(5).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x), raw=False)
        ts_rank_high = high.rolling(5).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x), raw=False)
        
        # correlation over 5 days
        corr = _correlation(ts_rank_vol, ts_rank_high, 5)
        
        # ts_max over 3 days
        return _ts_max(corr, 3)
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return -1 * result


@register_factor(
    "alpha033",
    category=FactorCategory.ALPHA101,
    description="Alpha#033: rank((-1 * ((1 - (open / close))^1)))",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha033(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#033.
    
    Formula: rank((-1 * ((1 - (open / close))^1)))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, open, close]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        return -1 * (1 - group["open"] / group["close"])
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return _rank(result)


@register_factor(
    "alpha038",
    category=FactorCategory.ALPHA101,
    description="Alpha#038: -1 * rank(Ts_Rank(close, 10)) * rank((close / open))",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha038(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#038.
    
    Formula: -1 * rank(Ts_Rank(close, 10)) * rank((close / open))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, open]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        close = group["close"]
        open_price = group["open"]
        
        # Ts_Rank(close, 10)
        ts_rank_close = close.rolling(10).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x), raw=False)
        
        # rank(close / open)
        ratio = close / open_price
        
        return ts_rank_close * ratio
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return -1 * _rank(result)


@register_factor(
    "alpha041",
    category=FactorCategory.ALPHA101,
    description="Alpha#041: sqrt(high * low) ^ volume",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha041(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#041.
    
    Formula: sqrt(high * low) ^ volume
    
    Note: This is a simplified version. The original formula may need normalization.
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, high, low, volume]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        return np.sqrt(group["high"] * group["low"])
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return _rank(result)


@register_factor(
    "alpha042",
    category=FactorCategory.ALPHA101,
    description="Alpha#042: rank(high - close) * rank(open - close)",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha042(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#042.
    
    Formula: rank(high - close) * rank(open - close)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, high, open, close]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        high = group["high"]
        open_price = group["open"]
        close = group["close"]
        
        return (high - close) * (open_price - close)
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return _rank(result)


@register_factor(
    "alpha044",
    category=FactorCategory.ALPHA101,
    description="Alpha#044: -1 * correlation(high, rank(volume), 5)",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha044(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#044.
    
    Formula: -1 * correlation(high, rank(volume), 5)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, high, volume]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        high = group["high"]
        rank_vol = _rank(group["volume"])
        return _correlation(high, rank_vol, 5)
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return -1 * result


@register_factor(
    "alpha047",
    category=FactorCategory.ALPHA101,
    description="Alpha#047: ((rank((1/close)) * volume) / adv20) * (high * rank(high-close) / ts_mean(high,5))",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha047(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#047 (simplified).
    
    Formula: rank(1/close) * volume_ratio * high_factor
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, volume, high]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        close = group["close"]
        volume = group["volume"]
        high = group["high"]
        
        # rank(1/close)
        rank_inv_close = _rank(1 / close)
        
        # volume / adv20
        adv20 = _sma(volume, 20)
        vol_ratio = volume / adv20.replace(0, np.nan)
        
        # high * rank(high - close) / ts_mean(high, 5)
        rank_high_close = _rank(high - close)
        mean_high_5 = _sma(high, 5)
        high_factor = high * rank_high_close / mean_high_5.replace(0, np.nan)
        
        return rank_inv_close * vol_ratio * high_factor
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "alpha053",
    category=FactorCategory.ALPHA101,
    description="Alpha#053: -1 * delta((((close - low) - (high - close)) / (close - low)), 9)",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha053(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#053.
    
    Formula: -1 * delta((((close - low) - (high - close)) / (close - low)), 9)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, high, low]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        close = group["close"]
        high = group["high"]
        low = group["low"]
        
        numerator = (close - low) - (high - close)
        denominator = close - low
        
        ratio = numerator / denominator.replace(0, np.nan)
        return _delta(ratio, 9)
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return -1 * result


@register_factor(
    "alpha054",
    category=FactorCategory.ALPHA101,
    description="Alpha#054: -1 * (low - close) * (open^5) / ((low - high) * (close^5))",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha054(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#054.
    
    Formula: -1 * (low - close) * (open^5) / ((low - high) * (close^5))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, open, high, low, close]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        open_price = group["open"]
        high = group["high"]
        low = group["low"]
        close = group["close"]
        
        numerator = (low - close) * (open_price ** 5)
        denominator = (low - high) * (close ** 5)
        
        return numerator / denominator.replace(0, np.nan)
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return -1 * result


@register_factor(
    "alpha060",
    category=FactorCategory.ALPHA101,
    description="Alpha#060: -1 * rank((2*scale(rank(argmax(close,10))) - scale(rank(argmin(close,10)))))",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha060(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#060 (simplified).
    
    Formula: -1 * rank(2*rank(argmax(close,10)) - rank(argmin(close,10)))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        close = group["close"]
        
        argmax = _ts_argmax(close, 10)
        argmin = _ts_argmin(close, 10)
        
        return 2 * _rank(argmax) - _rank(argmin)
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return -1 * _rank(result)


@register_factor(
    "alpha066",
    category=FactorCategory.ALPHA101,
    description="Alpha#066: -1 * ((rank(decay_linear(delta(open, 1), 15)) + rank(decay_linear(correlation(volume, open, 10), 5))) * -1)",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha066(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#066.
    
    Formula: rank(decay_linear(delta(open, 1), 15)) + rank(decay_linear(correlation(volume, open, 10), 5))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, open, volume]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        open_price = group["open"]
        volume = group["volume"]
        
        # rank(decay_linear(delta(open, 1), 15))
        delta_open = _delta(open_price, 1)
        decay_delta = _decay_linear(delta_open, 15)
        r1 = _rank(decay_delta)
        
        # rank(decay_linear(correlation(volume, open, 10), 5))
        corr_vol_open = _correlation(volume, open_price, 10)
        decay_corr = _decay_linear(corr_vol_open, 5)
        r2 = _rank(decay_corr)
        
        return r1 + r2
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "alpha070",
    category=FactorCategory.ALPHA101,
    description="Alpha#070: rank(delta(close, 1) * (1 - rank(decay_linear(volume/adv20, 5))))",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha070(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#070.
    
    Formula: rank(delta(close, 1) * (1 - rank(decay_linear(volume/adv20, 5))))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, volume]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        close = group["close"]
        volume = group["volume"]
        
        # delta(close, 1)
        delta_close = _delta(close, 1)
        
        # volume / adv20
        adv20 = _sma(volume, 20)
        vol_ratio = volume / adv20.replace(0, np.nan)
        
        # decay_linear(volume/adv20, 5)
        decay_vol = _decay_linear(vol_ratio, 5)
        
        # 1 - rank(decay_vol)
        factor = delta_close * (1 - _rank(decay_vol))
        
        return factor
    
    result = data.groupby("ts_code", group_keys=False).apply(_calc)
    return _rank(result)


@register_factor(
    "alpha074",
    category=FactorCategory.ALPHA101,
    description="Alpha#074: (rank(correlation(close, sum(adv20, 5), 10)) < rank(delta(close, 4))) * -1",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha074(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#074.
    
    Formula: (rank(correlation(close, sum(adv20, 5), 10)) < rank(delta(close, 4))) * -1
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, volume]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        close = group["close"]
        volume = group["volume"]
        
        # adv20
        adv20 = _sma(volume, 20)
        
        # sum(adv20, 5)
        sum_adv20 = _sum(adv20, 5)
        
        # correlation(close, sum(adv20, 5), 10)
        corr = _correlation(close, sum_adv20, 10)
        
        # delta(close, 4)
        delta_close = _delta(close, 4)
        
        # Compare ranks
        r1 = _rank(corr)
        r2 = _rank(delta_close)
        
        return pd.Series(np.where(r1 < r2, -1, 0), index=close.index)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "alpha081",
    category=FactorCategory.ALPHA101,
    description="Alpha#081: (rank(Log(product(rank((rank(correlation(volume, close, 10))^4)), 15))) < rank(correlation(rank(vwap), rank(volume), 5))) * -1",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha081(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#081 (simplified).
    
    Simplified version focusing on correlation between volume and close.
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, volume, vwap/amount]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        close = group["close"]
        volume = group["volume"]
        
        # rank(correlation(volume, close, 10))^4
        corr = _correlation(volume, close, 10)
        rank_corr = _rank(corr) ** 4
        
        # Log(product(..., 15))
        log_product = _log(_product(rank_corr, 15))
        
        # Use amount as vwap proxy if available
        if "amount" in group.columns:
            vwap = group["amount"] / volume.replace(0, np.nan)
        else:
            vwap = (group["high"] + group["low"] + close) / 3
        
        # correlation(rank(vwap), rank(volume), 5)
        corr2 = _correlation(_rank(vwap), _rank(volume), 5)
        
        r1 = _rank(log_product)
        r2 = _rank(corr2)
        
        return pd.Series(np.where(r1 < r2, -1, 0), index=close.index)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "alpha085",
    category=FactorCategory.ALPHA101,
    description="Alpha#085: rank(correlation(high*0.876703+close*(1-0.876703), adv30, 9.61331))^rank(correlation(Ts_Rank(high+low+close)/3, 3.70596), Ts_Rank(volume, 10.1595), 7.11408))",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha085(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#085 (simplified).
    
    Simplified version using correlation between price and volume.
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, high, low, close, volume]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        high = group["high"]
        low = group["low"]
        close = group["close"]
        volume = group["volume"]
        
        # Weighted price
        price = high * 0.876703 + close * (1 - 0.876703)
        
        # adv30
        adv30 = _sma(volume, 30)
        
        # Correlation 1
        corr1 = _rank(_correlation(price, adv30, 10))
        
        # Typical price rank
        typical = (high + low + close) / 3
        ts_rank_typical = typical.rolling(4).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x), raw=False)
        
        # Volume rank
        ts_rank_vol = volume.rolling(10).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x), raw=False)
        
        # Correlation 2
        corr2 = _rank(_correlation(ts_rank_typical, ts_rank_vol, 7))
        
        return corr1 ** corr2
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "alpha092",
    category=FactorCategory.ALPHA101,
    description="Alpha#092: min(Ts_Rank(decay_linear(delta(close, 1), 15), 20), Ts_Rank(decay_linear(correlation(close, adv30, 4), 2), 5))",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha092(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#092.
    
    Formula: min(Ts_Rank(decay_linear(delta(close, 1), 15), 20), Ts_Rank(decay_linear(correlation(close, adv30, 4), 2), 5))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, close, volume]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        close = group["close"]
        volume = group["volume"]
        
        # Part 1: Ts_Rank(decay_linear(delta(close, 1), 15), 20)
        delta_close = _delta(close, 1)
        decay_delta = _decay_linear(delta_close, 15)
        ts_rank1 = decay_delta.rolling(20).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x), raw=False)
        
        # Part 2: Ts_Rank(decay_linear(correlation(close, adv30, 4), 2), 5)
        adv30 = _sma(volume, 30)
        corr = _correlation(close, adv30, 4)
        decay_corr = _decay_linear(corr, 2)
        ts_rank2 = decay_corr.rolling(5).apply(lambda x: pd.Series(x).rank().iloc[-1] / len(x), raw=False)
        
        return pd.concat([ts_rank1, ts_rank2], axis=1).min(axis=1)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "alpha094",
    category=FactorCategory.ALPHA101,
    description="Alpha#094: rank((open - ts_min(open, 12))) < -1 * rank((open - ts_max(open, 12)))",
    direction=FactorDirection.SHORT,
    params={},
)
def compute_alpha094(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#094.
    
    Formula: rank((open - ts_min(open, 12))) < -1 * rank((open - ts_max(open, 12)))
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, open]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        open_price = group["open"]
        
        # rank(open - ts_min(open, 12))
        ts_min = _ts_min(open_price, 12)
        r1 = _rank(open_price - ts_min)
        
        # -1 * rank(open - ts_max(open, 12))
        ts_max = _ts_max(open_price, 12)
        r2 = -1 * _rank(open_price - ts_max)
        
        return pd.Series(np.where(r1 < r2, -1, 0), index=open_price.index)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "alpha098",
    category=FactorCategory.ALPHA101,
    description="Alpha#098: rank(decay_linear(correlation(vwap, adv5, 2), 5)) - rank(decay_linear(Ts_Rank(Ts_ArgMin(correlation(rank(open), rank(adv15), 20), 5), 15), 10))",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha098(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#098 (simplified).
    
    Simplified version using correlation between vwap and volume.
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, open, close, volume, amount]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        open_price = group["open"]
        close = group["close"]
        volume = group["volume"]
        
        # Use typical price as vwap proxy
        vwap = (group["high"] + group["low"] + close) / 3
        
        # Part 1: rank(decay_linear(correlation(vwap, adv5, 2), 5))
        adv5 = _sma(volume, 5)
        corr1 = _correlation(vwap, adv5, 2)
        decay1 = _decay_linear(corr1, 5)
        r1 = _rank(decay1)
        
        # Part 2: simplified
        adv15 = _sma(volume, 15)
        corr2 = _correlation(_rank(open_price), _rank(adv15), 20)
        argmin = _ts_argmin(corr2, 5)
        decay2 = _decay_linear(argmin, 15)
        r2 = _rank(decay2)
        
        return r1 - r2
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)


@register_factor(
    "alpha101",
    category=FactorCategory.ALPHA101,
    description="Alpha#101: (close - open) / ((high - low) + 0.001)",
    direction=FactorDirection.LONG,
    params={},
)
def compute_alpha101(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alpha#101.
    
    Formula: (close - open) / ((high - low) + 0.001)
    
    Args:
        data: DataFrame with columns [ts_code, trade_date, open, high, low, close]
    
    Returns:
        Series with alpha values
    """
    def _calc(group):
        open_price = group["open"]
        high = group["high"]
        low = group["low"]
        close = group["close"]
        
        return (close - open_price) / (high - low + 0.001)
    
    return data.groupby("ts_code", group_keys=False).apply(_calc)
