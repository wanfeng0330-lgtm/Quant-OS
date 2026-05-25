"""Financial report ORM model."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base, TimestampMixin, generate_uuid


class FinancialReportModel(TimestampMixin, Base):
    __tablename__ = "financial_reports"
    __table_args__ = (
        # Unique per stock per fiscal year per report type
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(10), nullable=False)  # Q1, H1, Q3, Annual
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    announce_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_revenue: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    net_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    net_profit_deducted: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    total_assets: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    total_liabilities: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    total_equity: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    eps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    roa: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    net_margin: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    current_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    debt_to_asset: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    cash_flow_operating: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
