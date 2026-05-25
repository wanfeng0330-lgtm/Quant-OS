"""Market API response DTOs."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel


class StockResponse(BaseModel):
    ts_code: str
    symbol: str
    name: str
    exchange: str
    board: str
    industry: str | None = None
    is_st: bool = False
    is_hs: bool = False
    list_date: str | None = None
    total_share: float | None = None
    float_share: float | None = None
    status: str = "active"


class OHLCVResponse(BaseModel):
    ts_code: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    pre_close: float | None = None
    change: float | None = None
    pct_chg: float | None = None
    volume: float
    amount: float | None = None
    turnover_rate: float | None = None
    is_limit_up: bool | None = None
    is_limit_down: bool | None = None
    is_suspended: bool | None = None


class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    size: int


class SyncResponse(BaseModel):
    job_id: str
    status: str
    message: str
    details: dict[str, Any] | None = None


class CalendarDayResponse(BaseModel):
    date: str
    is_open: bool


class SearchResult(BaseModel):
    ts_code: str
    symbol: str
    name: str
    exchange: str
