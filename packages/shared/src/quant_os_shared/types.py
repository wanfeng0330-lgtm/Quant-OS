"""Core type definitions for AI Quant Research OS."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, NewType

from pydantic import Field

# Stock code types
StockCode = NewType("StockCode", str)  # e.g., "000001.SZ"
StockSymbol = NewType("StockSymbol", str)  # e.g., "000001"
TradeDate = NewType("TradeDate", date)
ExchangeCode = NewType("ExchangeCode", str)  # SSE, SZSE, BSE

# Financial types
Price = NewType("Price", Decimal)
Volume = NewType("Volume", Decimal)
Amount = NewType("Amount", Decimal)
Percentage = NewType("Percentage", float)  # 0-100 range

# ID types
UUID4 = Annotated[str, Field(default_factory=lambda: str(uuid.uuid4()))]


class OHLCVBar:
    """Represents a single OHLCV bar."""
    def __init__(
        self,
        ts_code: str,
        trade_date: date,
        open: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: Decimal,
        amount: Decimal,
        pre_close: Decimal | None = None,
        pct_chg: float | None = None,
    ) -> None:
        self.ts_code = ts_code
        self.trade_date = trade_date
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.amount = amount
        self.pre_close = pre_close
        self.pct_chg = pct_chg
