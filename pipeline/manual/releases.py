"""Release calendars for the hand-entered reports: when is the report for month M normally out?

Dates are approximate (holidays outside the US federal calendar are ignored); ``MANUAL_GRACE_DAYS`` in
``config.py`` absorbs the difference.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

from pandas.tseries.holiday import USFederalHolidayCalendar

ORDINAL = {1: "1st", 2: "2nd", 3: "3rd"}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def add_months(month: str, n: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def month_of(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


@lru_cache(maxsize=64)
def _us_holidays(year: int) -> frozenset[date]:
    days = USFederalHolidayCalendar().holidays(start=f"{year}-01-01", end=f"{year}-12-31")
    return frozenset(d.date() for d in days)


def _is_business_day(day: date, us_holidays: bool) -> bool:
    return day.weekday() < 5 and not (us_holidays and day in _us_holidays(day.year))


@dataclass(frozen=True)
class ReleaseRule:
    """``kind``: ``business_day`` (nth business day of the next month), ``weekday`` (nth given weekday of
    the next month) or ``month_end`` (last day of the reference month)."""

    kind: str
    n: int = 1
    weekday: int = 1
    us_holidays: bool = True

    def due_date(self, month: str) -> date:
        y, m = int(month[:4]), int(month[5:7])
        if self.kind == "month_end":
            return date(y, m, calendar.monthrange(y, m)[1])
        nxt = add_months(month, 1)
        day = date(int(nxt[:4]), int(nxt[5:7]), 1)
        if self.kind == "business_day":
            count = 0
            while True:
                if _is_business_day(day, self.us_holidays):
                    count += 1
                    if count == self.n:
                        return day
                day += timedelta(days=1)
        if self.kind == "weekday":
            day += timedelta(days=(self.weekday - day.weekday()) % 7)
            return day + timedelta(weeks=self.n - 1)
        raise ValueError(f"unknown release rule {self.kind}")

    def latest_released_month(self, today: date) -> str:
        """The most recent reference month whose report should be out by ``today``."""
        month = month_of(today)
        while self.due_date(month) > today:
            month = add_months(month, -1)
        return month

    def describe(self) -> str:
        if self.kind == "month_end":
            return "last day of the month"
        nth = ORDINAL.get(self.n, f"{self.n}th")
        if self.kind == "business_day":
            return f"{nth} business day of the following month"
        return f"{nth} {WEEKDAYS[self.weekday]} of the following month"


ISM_MANUFACTURING = ReleaseRule("business_day", n=1)
ISM_SERVICES = ReleaseRule("business_day", n=3)
NFIB = ReleaseRule("weekday", n=2, weekday=1)
NBS = ReleaseRule("month_end", us_holidays=False)
RATINGDOG_MANUFACTURING = ReleaseRule("business_day", n=1, us_holidays=False)
RATINGDOG_SERVICES = ReleaseRule("business_day", n=3, us_holidays=False)
