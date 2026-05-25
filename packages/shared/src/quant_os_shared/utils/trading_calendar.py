"""A-share trading calendar utilities."""

from __future__ import annotations

from datetime import date, timedelta


class TradingCalendar:
    """A-share trading calendar.
    
    In production, this should load from database.
    This implementation provides basic weekend filtering.
    """

    def __init__(self, holidays: set[date] | None = None) -> None:
        self._holidays = holidays or set()

    def is_trading_day(self, d: date) -> bool:
        if d.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        if d in self._holidays:
            return False
        return True

    def get_previous_trading_day(self, d: date) -> date:
        prev = d - timedelta(days=1)
        while not self.is_trading_day(prev):
            prev -= timedelta(days=1)
        return prev

    def get_next_trading_day(self, d: date) -> date:
        next_day = d + timedelta(days=1)
        while not self.is_trading_day(next_day):
            next_day += timedelta(days=1)
        return next_day

    def get_trading_days(self, start: date, end: date) -> list[date]:
        days: list[date] = []
        current = start
        while current <= end:
            if self.is_trading_day(current):
                days.append(current)
            current += timedelta(days=1)
        return days

    def get_trading_days_count(self, start: date, end: date) -> int:
        return len(self.get_trading_days(start, end))

    def add_holidays(self, holidays: list[date]) -> None:
        self._holidays.update(holidays)
