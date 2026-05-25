"""Strategy and Backtest ORM models."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base, TimestampMixin, generate_uuid


class StrategyModel(TimestampMixin, Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # alpha, timing, portfolio
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    stock_pool: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rebalance_freq: Mapped[str | None] = mapped_column(String(10), nullable=True)  # daily, weekly, monthly
    max_holdings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.0003"))
    slippage_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.001"))
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BacktestRunModel(TimestampMixin, Base):
    __tablename__ = "backtest_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    strategy_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    benchmark_code: Mapped[str | None] = mapped_column(String(16), nullable=True, default="000300.SH")
    engine: Mapped[str | None] = mapped_column(String(50), nullable=True, default="internal")
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Performance metrics
    annual_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    calmar_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_loss_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_turnover: Mapped[float | None] = mapped_column(Float, nullable=True)
    alpha: Mapped[float | None] = mapped_column(Float, nullable=True)
    beta: Mapped[float | None] = mapped_column(Float, nullable=True)
    information_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    excess_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Time series data
    nav_series: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    drawdown_series: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    monthly_returns: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    position_history: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trade_log: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Error handling
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
