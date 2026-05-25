"""Trading calendar ORM model."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base


class TradingCalendarModel(Base):
    __tablename__ = "trading_calendar"

    cal_date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False, default="ALL")
    pre_trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
