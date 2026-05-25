"""Factor ORM models."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base, TimestampMixin, generate_uuid


class FactorModel(TimestampMixin, Base):
    __tablename__ = "factors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    factor_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # alpha101, alpha191, technical, custom
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction: Mapped[int] = mapped_column(SmallInteger, default=1)  # 1=long, -1=short
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    registered_by: Mapped[str | None] = mapped_column(String(100), nullable=True)


class FactorValueModel(Base):
    __tablename__ = "factor_values"

    ts_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    factor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[float | None] = mapped_column(Float, nullable=True)
    zscore: Mapped[float | None] = mapped_column(Float, nullable=True)


class FactorAnalysisResultModel(TimestampMixin, Base):
    __tablename__ = "factor_analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    factor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    analysis_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ic_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    ic_std: Mapped[float | None] = mapped_column(Float, nullable=True)
    icir: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank_ic_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank_icir: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover: Mapped[float | None] = mapped_column(Float, nullable=True)
    long_short_sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    layer_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ic_series: Mapped[dict | None] = mapped_column(JSON, nullable=True)
