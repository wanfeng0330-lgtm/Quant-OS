"""A-share market constants and configuration."""

from enum import Enum


class Exchange(str, Enum):
    """Chinese stock exchanges."""
    SSE = "SSE"       # Shanghai Stock Exchange
    SZSE = "SZSE"     # Shenzhen Stock Exchange
    BSE = "BSE"       # Beijing Stock Exchange


class Board(str, Enum):
    """Stock board types."""
    MAIN = "main"           # Main board (主板)
    CHINEXT = "chinext"     # ChiNext (创业板)
    STAR = "star"           # STAR Market (科创板)
    BSE = "bse"             # BSE (北交所)


class StockStatus(str, Enum):
    """Stock trading status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELISTED = "delisted"
    ST = "st"
    STAR_ST = "*st"


class ReportType(str, Enum):
    """Financial report types."""
    Q1 = "Q1"
    H1 = "H1"
    Q3 = "Q3"
    ANNUAL = "Annual"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class BacktestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentType(str, Enum):
    """AI Agent types."""
    RESEARCH = "research"
    FACTOR = "factor"
    NEWS = "news"
    BACKTEST = "backtest"
    RISK = "risk"
    PORTFOLIO = "portfolio"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# A-share trading rules
TRADING_RULES = {
    "t_plus_1": True,  # T+1 trading
    "price_limit_main": 0.10,  # 10% for main board
    "price_limit_chinext": 0.20,  # 20% for ChiNext
    "price_limit_star": 0.20,  # 20% for STAR
    "price_limit_bse": 0.30,  # 30% for BSE
    "min_lot_size": 100,  # Minimum trading unit (手 = 100 shares)
    "trading_hours": {
        "morning_open": "09:30",
        "morning_close": "11:30",
        "afternoon_open": "13:00",
        "afternoon_close": "15:00",
    },
    "auction_hours": {
        "call_auction_start": "09:15",
        "call_auction_end": "09:25",
        "closing_auction_start": "14:57",
        "closing_auction_end": "15:00",
    },
}

# Default costs
DEFAULT_COMMISSION_RATE = 0.0003  # 万三 (0.03%)
DEFAULT_SLIPPAGE_RATE = 0.001   # 千一 (0.1%)
DEFAULT_STAMP_DUTY_RATE = 0.001 # 千一 (0.1%, sell-side only)
DEFAULT_MIN_COMMISSION = 5.0    # 最低佣金 5元

# Major indices
MAJOR_INDICES = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
    "000300.SH": "沪深300",
    "000905.SH": "中证500",
    "000852.SH": "中证1000",
}

# Shenwan industry classification levels
SHENWAN_LEVELS = [1, 2, 3]
