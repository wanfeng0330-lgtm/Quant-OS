"""Stock ORM model."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base, TimestampMixin, generate_uuid


class StockModel(TimestampMixin, Base):
    __tablename__ = "stocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    ts_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)  # SSE, SZSE, BSE
    board: Mapped[str] = mapped_column(String(20), nullable=False, default="main")
    list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delist_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_st: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hs: Mapped[bool] = mapped_column(Boolean, default=False)
    total_share: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    float_share: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
