"""Vectorized backtest engine implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from quant_os_shared.errors import BacktestExecutionError, BacktestConfigError

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Backtest configuration."""
    
    initial_capital: Decimal = Decimal("1000000")  # 100万初始资金
    commission_rate: Decimal = Decimal("0.0003")  # 万分之三佣金
    slippage_rate: Decimal = Decimal("0.001")  # 千分之一滑点
    stamp_tax_rate: Decimal = Decimal("0.001")  # 千分之一印花税（卖出）
    min_commission: Decimal = Decimal("5")  # 最低佣金5元
    
    # A股交易规则
    t_plus_1: bool = True  # T+1交易制度
    price_limit: bool = True  # 涨跌停限制
    price_limit_pct: float = 0.10  # 涨跌停幅度（10%）
    suspended_trading_penalty: bool = True  # 停牌股票处理
    
    # 回测参数
    benchmark_code: str = "000300.SH"  # 基准指数
    rebalance_freq: str = "daily"  # 调仓频率
    
    def validate(self) -> None:
        """Validate configuration."""
        if self.initial_capital <= 0:
            raise BacktestConfigError("Initial capital must be positive")
        if self.commission_rate < 0:
            raise BacktestConfigError("Commission rate cannot be negative")
        if self.slippage_rate < 0:
            raise BacktestConfigError("Slippage rate cannot be negative")
        if self.stamp_tax_rate < 0:
            raise BacktestConfigError("Stamp tax rate cannot be negative")
        if not 0 < self.price_limit_pct < 1:
            raise BacktestConfigError("Price limit percentage must be between 0 and 1")


@dataclass
class BacktestResult:
    """Backtest execution result."""
    
    # 基本信息
    start_date: date
    end_date: date
    trading_days: int
    
    # 收益指标
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    
    # 风险指标
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    volatility: float = 0.0
    downside_risk: float = 0.0
    
    # 风险调整收益
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    information_ratio: float = 0.0
    
    # 交易统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_loss_ratio: float = 0.0
    avg_turnover: float = 0.0
    
    # Alpha/Beta
    alpha: float = 0.0
    beta: float = 0.0
    
    # 时间序列数据
    nav_series: list[dict[str, Any]] = field(default_factory=list)
    drawdown_series: list[dict[str, Any]] = field(default_factory=list)
    monthly_returns: list[dict[str, Any]] = field(default_factory=list)
    position_history: list[dict[str, Any]] = field(default_factory=list)
    trade_log: list[dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_date": str(self.start_date),
            "end_date": str(self.end_date),
            "trading_days": self.trading_days,
            "total_return": round(self.total_return, 6),
            "annual_return": round(self.annual_return, 6),
            "benchmark_return": round(self.benchmark_return, 6),
            "excess_return": round(self.excess_return, 6),
            "max_drawdown": round(self.max_drawdown, 6),
            "max_drawdown_duration": self.max_drawdown_duration,
            "volatility": round(self.volatility, 6),
            "downside_risk": round(self.downside_risk, 6),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "information_ratio": round(self.information_ratio, 4),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "profit_loss_ratio": round(self.profit_loss_ratio, 4),
            "avg_turnover": round(self.avg_turnover, 6),
            "alpha": round(self.alpha, 6),
            "beta": round(self.beta, 6),
        }


class VectorizedBacktestEngine:
    """Vectorized backtest engine for A-share strategies.
    
    This engine uses vectorized operations with pandas/numpy for fast backtesting.
    It implements A-share specific trading rules including:
    - T+1 trading settlement
    - Price limits (涨跌停)
    - Commission and slippage modeling
    - Stamp tax on sells
    """
    
    def __init__(self, config: BacktestConfig | None = None):
        """Initialize engine with configuration."""
        self.config = config or BacktestConfig()
        self.config.validate()
    
    def run(
        self,
        signals: pd.DataFrame,
        market_data: pd.DataFrame,
        benchmark_data: pd.DataFrame | None = None,
    ) -> BacktestResult:
        """Run backtest with given signals and market data.
        
        Args:
            signals: DataFrame with columns [ts_code, trade_date, signal, weight]
                    signal: 1 (buy), -1 (sell), 0 (hold)
                    weight: portfolio weight (0-1)
            market_data: DataFrame with columns [ts_code, trade_date, open, high, low, close, volume, pct_chg]
            benchmark_data: Optional benchmark DataFrame
            
        Returns:
            BacktestResult with performance metrics
        """
        logger.info("Starting backtest from %s to %s", 
                   signals["trade_date"].min(), signals["trade_date"].max())
        
        # Validate input data
        self._validate_input(signals, market_data)
        
        # Prepare data
        signals = self._prepare_signals(signals)
        market_data = self._prepare_market_data(market_data)
        
        # Merge signals with market data
        merged = pd.merge(
            signals, market_data,
            on=["ts_code", "trade_date"],
            how="inner",
        )
        
        if merged.empty:
            raise BacktestExecutionError("No data after merging signals and market data")
        
        # Get unique trading dates
        trading_dates = sorted(merged["trade_date"].unique())
        
        # Initialize portfolio
        portfolio = self._initialize_portfolio(trading_dates[0])
        
        # Run simulation
        nav_series = []
        drawdown_series = []
        position_history = []
        trade_log = []
        
        for i, current_date in enumerate(trading_dates):
            # Get current day data
            day_data = merged[merged["trade_date"] == current_date]
            
            # Apply trading rules
            day_data = self._apply_trading_rules(day_data, portfolio)
            
            # Execute trades
            trades = self._execute_trades(day_data, portfolio, current_date)
            trade_log.extend(trades)
            
            # Update portfolio
            self._update_portfolio(portfolio, day_data, current_date)
            
            # Record NAV
            nav = self._calculate_nav(portfolio)
            nav_series.append({
                "date": str(current_date),
                "nav": nav,
                "cash": float(portfolio["cash"]),
                "market_value": float(portfolio["market_value"]),
            })
            
            # Record positions
            for ts_code, position in portfolio["positions"].items():
                position_history.append({
                    "date": str(current_date),
                    "ts_code": ts_code,
                    "shares": position["shares"],
                    "cost": float(position["cost"]),
                    "market_value": float(position["market_value"]),
                })
            
            # Calculate drawdown
            if nav_series:
                peak = max(item["nav"] for item in nav_series)
                drawdown = (nav - peak) / peak if peak > 0 else 0
                drawdown_series.append({
                    "date": str(current_date),
                    "drawdown": drawdown,
                })
        
        # Calculate performance metrics
        result = self._calculate_metrics(
            nav_series=nav_series,
            drawdown_series=drawdown_series,
            trade_log=trade_log,
            benchmark_data=benchmark_data,
            start_date=trading_dates[0],
            end_date=trading_dates[-1],
        )
        
        logger.info(
            "Backtest completed: total_return=%.2f%%, sharpe=%.2f, max_drawdown=%.2f%%",
            result.total_return * 100, result.sharpe_ratio, result.max_drawdown * 100,
        )
        
        return result
    
    def _validate_input(self, signals: pd.DataFrame, market_data: pd.DataFrame) -> None:
        """Validate input data."""
        required_signal_cols = ["ts_code", "trade_date", "signal"]
        for col in required_signal_cols:
            if col not in signals.columns:
                raise BacktestConfigError(f"Signals missing required column: {col}")
        
        required_market_cols = ["ts_code", "trade_date", "open", "high", "low", "close", "volume"]
        for col in required_market_cols:
            if col not in market_data.columns:
                raise BacktestConfigError(f"Market data missing required column: {col}")
    
    def _prepare_signals(self, signals: pd.DataFrame) -> pd.DataFrame:
        """Prepare signals DataFrame."""
        signals = signals.copy()
        
        # Ensure trade_date is datetime
        if not pd.api.types.is_datetime64_any_dtype(signals["trade_date"]):
            signals["trade_date"] = pd.to_datetime(signals["trade_date"])
        
        # Add weight column if not present
        if "weight" not in signals.columns:
            # Equal weight for all signals
            signals["weight"] = signals.groupby("trade_date")["signal"].transform(
                lambda x: 1.0 / len(x) if len(x) > 0 else 0.0
            )
        
        return signals
    
    def _prepare_market_data(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Prepare market data DataFrame."""
        market_data = market_data.copy()
        
        # Ensure trade_date is datetime
        if not pd.api.types.is_datetime64_any_dtype(market_data["trade_date"]):
            market_data["trade_date"] = pd.to_datetime(market_data["trade_date"])
        
        # Add pct_chg if not present
        if "pct_chg" not in market_data.columns:
            market_data["pct_chg"] = market_data.groupby("ts_code")["close"].pct_change()
        
        return market_data
    
    def _initialize_portfolio(self, start_date: date) -> dict[str, Any]:
        """Initialize portfolio."""
        return {
            "cash": float(self.config.initial_capital),
            "positions": {},  # {ts_code: {shares, cost, market_value}}
            "market_value": 0.0,
            "total_value": float(self.config.initial_capital),
        }
    
    def _apply_trading_rules(
        self,
        day_data: pd.DataFrame,
        portfolio: dict[str, Any],
    ) -> pd.DataFrame:
        """Apply A-share trading rules."""
        day_data = day_data.copy()
        
        # Apply price limit rules
        if self.config.price_limit:
            day_data = self._apply_price_limits(day_data)
        
        # Apply T+1 rule
        if self.config.t_plus_1:
            day_data = self._apply_t_plus_1(day_data, portfolio)
        
        return day_data
    
    def _apply_price_limits(self, day_data: pd.DataFrame) -> pd.DataFrame:
        """Apply price limit rules (涨跌停).
        
        Different boards have different price limits:
        - Main board: 10%
        - ChiNext (创业板): 20%
        - STAR (科创板): 20%
        - BSE (北交所): 30%
        """
        if "pct_chg" not in day_data.columns:
            return day_data
        
        # Import board detection utility
        from quant_os_shared.utils.stock_code import get_board
        
        # Apply board-specific price limits
        def check_price_limit(row):
            ts_code = row["ts_code"]
            pct_chg = row["pct_chg"]
            
            # Get board type
            board = get_board(ts_code)
            
            # Determine price limit percentage
            if board == "chinext" or board == "star":
                limit_pct = 20.0  # 20% for ChiNext and STAR
            elif board == "bse":
                limit_pct = 30.0  # 30% for BSE
            else:
                limit_pct = 10.0  # 10% for main board
            
            # Check if at limit
            is_limit_up = pct_chg >= limit_pct
            is_limit_down = pct_chg <= -limit_pct
            
            return pd.Series({
                "is_limit_up": is_limit_up,
                "is_limit_down": is_limit_down,
                "price_limit_pct": limit_pct,
            })
        
        # Apply price limit check, replacing provider-supplied flags if present.
        limit_results = day_data.apply(check_price_limit, axis=1)
        for column in limit_results.columns:
            day_data[column] = limit_results[column].values
        
        return day_data
    
    def _apply_t_plus_1(
        self,
        day_data: pd.DataFrame,
        portfolio: dict[str, Any],
    ) -> pd.DataFrame:
        """Apply T+1 trading rule.
        
        Note: T+1 rule is enforced in _execute_trades by checking buy_date.
        This method can be used for additional T+1 related preprocessing if needed.
        """
        return day_data
    
    def _execute_trades(
        self,
        day_data: pd.DataFrame,
        portfolio: dict[str, Any],
        current_date: date,
    ) -> list[dict[str, Any]]:
        """Execute trades based on signals."""
        trades = []
        
        for _, row in day_data.iterrows():
            ts_code = row["ts_code"]
            signal = row["signal"]
            weight = row.get("weight", 0)
            
            if signal == 0:
                continue
            
            # Get current price
            price = row["close"]
            
            # Calculate target position value
            target_value = portfolio["total_value"] * weight
            
            # Get current position
            current_position = portfolio["positions"].get(ts_code, {
                "shares": 0,
                "cost": 0.0,
                "market_value": 0.0,
                "buy_date": None,  # Track buy date for T+1 rule
            })
            
            current_value = current_position["shares"] * price
            
            # Calculate trade amount
            trade_value = target_value - current_value
            
            if abs(trade_value) < 100:  # Minimum trade value
                continue
            
            # Check price limits
            if row.get("is_limit_up") and trade_value > 0:
                # Cannot buy at limit up
                continue
            if row.get("is_limit_down") and trade_value < 0:
                # Cannot sell at limit down
                continue
            
            # Determine trade direction
            if trade_value > 0:
                # Buy
                shares_to_buy = int(trade_value / price / 100) * 100  # Round to 100 shares
                if shares_to_buy > 0:
                    # Calculate costs
                    commission = max(
                        float(self.config.min_commission),
                        shares_to_buy * price * float(self.config.commission_rate)
                    )
                    slippage = shares_to_buy * price * float(self.config.slippage_rate)
                    total_cost = shares_to_buy * price + commission + slippage
                    
                    # Check if enough cash
                    if total_cost <= portfolio["cash"]:
                        # Execute buy
                        portfolio["cash"] -= total_cost
                        
                        # Update position
                        new_shares = current_position["shares"] + shares_to_buy
                        new_cost = (
                            (current_position["cost"] * current_position["shares"] + 
                             shares_to_buy * price) / new_shares
                        ) if new_shares > 0 else 0
                        
                        portfolio["positions"][ts_code] = {
                            "shares": new_shares,
                            "cost": new_cost,
                            "market_value": new_shares * price,
                            "buy_date": current_date,  # Record buy date for T+1 rule
                        }
                        
                        trades.append({
                            "date": str(current_date),
                            "ts_code": ts_code,
                            "direction": "buy",
                            "shares": shares_to_buy,
                            "price": price,
                            "amount": shares_to_buy * price,
                            "commission": commission,
                            "slippage": slippage,
                        })
            
            elif trade_value < 0:
                # Sell - check T+1 rule
                if self.config.t_plus_1 and current_position.get("buy_date") == current_date:
                    # Cannot sell stocks bought today (T+1 rule)
                    continue
                
                shares_to_sell = min(
                    int(-trade_value / price / 100) * 100,
                    current_position["shares"]
                )
                
                if shares_to_sell > 0:
                    # Calculate costs
                    commission = max(
                        float(self.config.min_commission),
                        shares_to_sell * price * float(self.config.commission_rate)
                    )
                    slippage = shares_to_sell * price * float(self.config.slippage_rate)
                    stamp_tax = shares_to_sell * price * float(self.config.stamp_tax_rate)
                    
                    # Execute sell
                    proceeds = shares_to_sell * price - commission - slippage - stamp_tax
                    portfolio["cash"] += proceeds
                    
                    # Update position
                    new_shares = current_position["shares"] - shares_to_sell
                    if new_shares == 0:
                        del portfolio["positions"][ts_code]
                    else:
                        portfolio["positions"][ts_code] = {
                            "shares": new_shares,
                            "cost": current_position["cost"],
                            "market_value": new_shares * price,
                            "buy_date": current_position.get("buy_date"),  # Preserve buy date
                        }
                    
                    trades.append({
                        "date": str(current_date),
                        "ts_code": ts_code,
                        "direction": "sell",
                        "shares": shares_to_sell,
                        "price": price,
                        "amount": shares_to_sell * price,
                        "commission": commission,
                        "slippage": slippage,
                        "stamp_tax": stamp_tax,
                    })
        
        return trades
    
    def _update_portfolio(
        self,
        portfolio: dict[str, Any],
        day_data: pd.DataFrame,
        current_date: date,
    ) -> None:
        """Update portfolio with current market values."""
        # Update market values for all positions
        for ts_code, position in portfolio["positions"].items():
            # Get current price
            stock_data = day_data[day_data["ts_code"] == ts_code]
            if not stock_data.empty:
                current_price = stock_data.iloc[0]["close"]
                position["market_value"] = position["shares"] * current_price
        
        # Calculate total market value
        portfolio["market_value"] = sum(
            pos["market_value"] for pos in portfolio["positions"].values()
        )
        
        # Calculate total portfolio value
        portfolio["total_value"] = portfolio["cash"] + portfolio["market_value"]
    
    def _calculate_nav(self, portfolio: dict[str, Any]) -> float:
        """Calculate net asset value."""
        initial_capital = float(self.config.initial_capital)
        return portfolio["total_value"] / initial_capital if initial_capital > 0 else 1.0
    
    def _calculate_metrics(
        self,
        nav_series: list[dict[str, Any]],
        drawdown_series: list[dict[str, Any]],
        trade_log: list[dict[str, Any]],
        benchmark_data: pd.DataFrame | None,
        start_date: date,
        end_date: date,
    ) -> BacktestResult:
        """Calculate performance metrics."""
        # Convert to numpy arrays for calculations
        navs = np.array([item["nav"] for item in nav_series])
        dates = [item["date"] for item in nav_series]
        
        # Calculate returns
        returns = np.diff(navs) / navs[:-1]
        
        # Basic metrics
        total_return = (navs[-1] / navs[0]) - 1 if len(navs) > 1 else 0
        trading_days = len(navs)
        years = trading_days / 252  # Approximate trading days per year
        
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Risk metrics
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
        downside_returns = returns[returns < 0]
        downside_risk = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 1 else 0
        
        # Drawdown metrics
        drawdowns = np.array([item["drawdown"] for item in drawdown_series])
        max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0
        
        # Calculate max drawdown duration
        max_drawdown_duration = 0
        current_duration = 0
        for dd in drawdowns:
            if dd < 0:
                current_duration += 1
                max_drawdown_duration = max(max_drawdown_duration, current_duration)
            else:
                current_duration = 0
        
        # Risk-adjusted returns
        risk_free_rate = 0.03  # Assume 3% risk-free rate
        excess_returns = returns - risk_free_rate / 252
        
        sharpe_ratio = (
            np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
            if len(excess_returns) > 1 and np.std(excess_returns) > 0
            else 0
        )
        
        sortino_ratio = (
            np.mean(excess_returns) / downside_risk * np.sqrt(252)
            if downside_risk > 0
            else 0
        )
        
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Trade statistics
        total_trades = len(trade_log)
        buy_trades = [t for t in trade_log if t["direction"] == "buy"]
        sell_trades = [t for t in trade_log if t["direction"] == "sell"]
        
        # Simple win/loss calculation (would need more sophisticated logic in reality)
        winning_trades = len([t for t in sell_trades if t.get("profit", 0) > 0])
        losing_trades = len(sell_trades) - winning_trades
        win_rate = winning_trades / len(sell_trades) if sell_trades else 0
        
        # Average turnover
        if trade_log:
            total_turnover = sum(t["amount"] for t in trade_log)
            avg_turnover = total_turnover / trading_days if trading_days > 0 else 0
        else:
            avg_turnover = 0
        
        # Benchmark metrics
        benchmark_return = 0
        alpha = 0
        beta = 0
        information_ratio = 0
        
        if benchmark_data is not None and not benchmark_data.empty:
            # Calculate benchmark return
            benchmark_returns = benchmark_data["pct_chg"].values / 100
            benchmark_total = np.prod(1 + benchmark_returns) - 1
            benchmark_return = benchmark_total
            
            # Calculate alpha and beta
            if len(returns) > 1 and len(benchmark_returns) > 1:
                # Align lengths
                min_len = min(len(returns), len(benchmark_returns))
                returns_aligned = returns[:min_len]
                benchmark_aligned = benchmark_returns[:min_len]
                
                # Calculate beta
                covariance = np.cov(returns_aligned, benchmark_aligned)
                beta = covariance[0, 1] / covariance[1, 1] if covariance[1, 1] != 0 else 0
                
                # Calculate alpha
                alpha = annual_return - (risk_free_rate + beta * (benchmark_return - risk_free_rate))
                
                # Information ratio
                excess_returns = returns_aligned - benchmark_aligned
                tracking_error = np.std(excess_returns) * np.sqrt(252)
                information_ratio = (
                    (annual_return - benchmark_return) / tracking_error
                    if tracking_error > 0
                    else 0
                )
        
        # Monthly returns
        monthly_returns = self._calculate_monthly_returns(nav_series)
        
        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            trading_days=trading_days,
            total_return=total_return,
            annual_return=annual_return,
            benchmark_return=benchmark_return,
            excess_return=total_return - benchmark_return,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_drawdown_duration,
            volatility=volatility,
            downside_risk=downside_risk,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            information_ratio=information_ratio,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            profit_loss_ratio=0.0,  # Would need more sophisticated calculation
            avg_turnover=avg_turnover,
            alpha=alpha,
            beta=beta,
            nav_series=nav_series,
            drawdown_series=drawdown_series,
            monthly_returns=monthly_returns,
            position_history=[],  # Would need to collect during simulation
            trade_log=trade_log,
        )
    
    def _calculate_monthly_returns(
        self,
        nav_series: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Calculate monthly returns."""
        if not nav_series:
            return []
        
        # Convert to DataFrame
        df = pd.DataFrame(nav_series)
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        
        # Resample to monthly
        try:
            monthly = df["nav"].resample("ME").last()
        except ValueError:
            monthly = df["nav"].resample("M").last()
        monthly_returns = monthly.pct_change().dropna()
        
        result = []
        for date, ret in monthly_returns.items():
            result.append({
                "month": date.strftime("%Y-%m"),
                "return": float(ret),
            })
        
        return result
