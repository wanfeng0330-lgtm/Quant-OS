"""Sector/Industry classification ORM models."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base, TimestampMixin, generate_uuid


class SectorIndustryModel(TimestampMixin, Base):
    __tablename__ = "sector_industry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)  # shenwan, citic
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sector_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(20), nullable=True)


class StockSectorMapModel(Base):
    __tablename__ = "stock_sector_map"

    ts_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True, primary_key=True)
    sector_code: Mapped[str] = mapped_column(String(20), nullable=False, primary_key=True)
    classification: Mapped[str] = mapped_column(String(20), nullable=False, primary_key=True)
    in_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    out_date: Mapped[date | None] = mapped_column(Date, nullable=True)
