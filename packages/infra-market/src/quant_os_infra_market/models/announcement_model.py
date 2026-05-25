"""Announcement ORM model."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base, TimestampMixin, generate_uuid


class AnnouncementModel(TimestampMixin, Base):
    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    ts_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    announce_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    announce_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
