"""Parse the official meeting calendars of the Fed, ECB, Bank of Japan and Bank of England.

Each parser takes the page's HTML and returns ``[(decision_date, detail), ...]``. They only read text, so a
layout change shows up as "no meetings found" (the pipeline then keeps the last good copy).
"""

from __future__ import annotations

import html as html_lib
import re
from datetime import date

MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        start=1,
    )
}


def month_number(name: str) -> int:
    """'Sept.' / 'Sep' / 'September' -> 9."""
    key = name.strip(" .").lower()
    for full, n in MONTHS.items():
        if full.startswith(key[:3]):
            return n
    raise ValueError(f"unknown month {name!r}")


def page_text(page: str) -> str:
    """Visible text of an HTML page on one line (scripts, styles and tags removed, entities decoded)."""
    page = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S | re.I)
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", page))
    return re.sub(r"\s+", " ", text.replace("\xa0", " "))


def fomc(page: str) -> list[tuple[date, str]]:
    """federalreserve.gov/monetarypolicy/fomccalendars.htm: one panel per year, month + 'day-day' (* = SEP)."""
    out = []
    parts = re.split(r"(\d{4}) FOMC Meetings", page)
    for i in range(1, len(parts), 2):
        year = int(parts[i])
        for month, days in re.findall(
            r"fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<",
            parts[i + 1],
            re.S,
        ):
            m = re.fullmatch(r"\s*(\d{1,2})(?:-(\d{1,2}))?(\*?)\s*", days)
            if not m:
                continue  # notation votes, unscheduled meetings
            end_month = month.split("/")[-1]
            end_day = int(m[2] or m[1])
            detail = "with Summary of Economic Projections" if m[3] else ""
            out.append((date(year, month_number(end_month), end_day), detail))
    return sorted(set(out))


def ecb(page: str) -> list[tuple[date, str]]:
    """ecb.europa.eu meeting calendar: 'dd/mm/yyyy Governing Council of the ECB: monetary policy meeting ...'.
    A two-day meeting decides on its last day."""
    days = sorted(
        {
            date(int(y), int(mo), int(d))
            for d, mo, y, what in re.findall(
                r"(\d{2})/(\d{2})/(\d{4})\s+(?=((?:(?!\d{2}/\d{2}/\d{4}).){0,120}))", page_text(page)
            )
            if "monetary policy meeting" in what.lower() and "non-monetary" not in what.lower()
        }
    )
    out = []
    for i, day in enumerate(days):
        if i + 1 < len(days) and (days[i + 1] - day).days == 1:
            continue  # day 1 of a two-day meeting
        out.append((day, "press conference after the decision"))
    return out


def boj(page: str) -> list[tuple[date, str]]:
    """boj.or.jp schedule: one table per year; meetings are 'Oct. 29 (Thurs.), 30 (Fri.)' (release columns
    hold single dates, so only pairs are meetings)."""
    text = page_text(page)
    out = []
    pair = re.compile(
        r"([A-Z][a-z]+)\.? (\d{1,2}) \([A-Za-z]+\.?\), (?:([A-Z][a-z]+)\.? )?(\d{1,2}) \([A-Za-z]+\.?\)"
    )
    sections = re.split(r"Table : (\d{4})", text)
    for i in range(1, len(sections), 2):
        year = int(sections[i])
        for m1, _d1, m2, d2 in pair.findall(sections[i + 1]):
            try:
                out.append((date(year, month_number(m2 or m1), int(d2)), "two-day meeting"))
            except ValueError:
                continue
    return sorted(set(out))


def boe(page: str) -> list[tuple[date, str]]:
    """bankofengland.co.uk upcoming MPC dates: '<year> confirmed dates' then 'Thursday 5 November ...'."""
    text = page_text(page)
    out = []
    sections = re.split(r"(\d{4}) (?:confirmed|provisional) dates", text)
    for i in range(1, len(sections), 2):
        year = int(sections[i])
        body = sections[i + 1]
        for day, month, rest in re.findall(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday) (\d{1,2}) ([A-Z][a-z]+) (?=(.{0,80}))", body
        ):
            detail = (
                "with Monetary Policy Report" if "Monetary Policy Report" in rest.split("Thursday")[0] else ""
            )
            out.append((date(year, month_number(month), int(day)), detail))
    return sorted(set(out))


CENTRAL_BANKS = {
    # id: (parser, title, region, url)
    "fomc": (
        fomc,
        "FOMC rate decision (Fed)",
        "US",
        "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    ),
    "ecb": (
        ecb,
        "ECB rate decision",
        "Euro area",
        "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html",
    ),
    "boj": (
        boj,
        "Bank of Japan policy decision",
        "Japan",
        "https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm",
    ),
    "boe": (
        boe,
        "Bank of England rate decision",
        "UK",
        "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates",
    ),
}
