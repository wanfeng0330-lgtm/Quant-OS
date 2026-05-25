"""Dragon-tiger list ORM model."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base, TimestampMixin, generate_uuid


class DragonTigerModel(TimestampMixin, Base):
    __tablename__ = "dragon_tiger_list"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    buy_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    sell_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    broker_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    broker_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # buy or sell
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
