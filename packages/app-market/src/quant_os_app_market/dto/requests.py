"""Market API request DTOs."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class SyncRequest(BaseModel):
    source: str = Field(default="akshare", description="Data source: akshare or tushare")
    data_type: str = Field(default="stock_list", description="Type: stock_list, ohlcv_daily, calendar, northbound, dragon_tiger, sector")
    ts_code: Optional[str] = Field(default=None, description="Stock code for targeted sync")
    trade_date: Optional[date] = Field(default=None, description="Specific date for sync")
    start_date: Optional[date] = Field(default=None)
    end_date: Optional[date] = Field(default=None)
    year: Optional[int] = Field(default=None, description="Year for calendar sync")
