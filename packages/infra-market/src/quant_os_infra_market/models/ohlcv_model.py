"""OHLCV ORM models (daily + minute bars)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base


class OHLCVDailyModel(Base):
    __tablename__ = "ohlcv_daily"

    ts_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    change: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    is_limit_up: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_limit_down: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_suspended: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )


class OHLCVMinuteModel(Base):
    __tablename__ = "ohlcv_minute"

    ts_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    freq: Mapped[str] = mapped_column(String(5), primary_key=True)  # 1m, 5m, 15m, 30m, 60m
    open: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
