"""Northbound capital flow ORM model."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base, generate_uuid


class NorthboundFlowModel(Base):
    __tablename__ = "northbound_flow"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ts_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)  # NULL = aggregate
    channel: Mapped[str] = mapped_column(String(10), nullable=False)  # sh or sz
    buy_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    sell_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    hold_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    hold_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
