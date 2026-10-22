"""Catalyst calendar (``site/data/calendar.json``): what is due in the next months, with the 20-60 day window of
a new trade highlighted (lessons 1-2: a trade idea needs its catalysts and timing).

- US data releases: FRED's release calendar (CPI, payrolls, GDP, PCE, ...). BLS blocks automated requests,
  FRED republishes the official schedules.
- Central banks: the Fed, ECB, Bank of Japan and Bank of England meeting pages (``parsers.py``).
- Hand-entered reports (ISM, NFIB, China PMIs): the release rules in ``pipeline.manual.releases``.

Every source is cached in ``data/raw/calendar/``; a failing source keeps its last good copy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from ..fetchers.fred import FredClient
from ..http import FetchError, HttpClient, redact
from ..manual import releases as rel
from ..store import RawCache, iso, utc_now
from . import parsers

log = logging.getLogger("pipeline.calendar")

WINDOW = (20, 60)  # the holding period of a trade opened today (lesson 1)
LOOKBACK_DAYS = 7  # keep last week's events (what just happened)
HORIZON_DAYS = 120

# FRED release id -> (title, importance, related Macro Desk signals). IDs verified 2026-10-22.
FRED_RELEASES = {
    10: ("CPI (consumer prices)", "high", ["real_rate"]),
    50: ("Employment Situation (payrolls, unemployment)", "high", []),
    53: ("GDP", "high", []),
    54: ("Personal income & outlays (PCE inflation)", "medium", []),
    46: ("PPI (producer prices)", "medium", []),
    9: ("Retail sales", "medium", []),
    13: ("Industrial production", "medium", []),
    95: ("Durable goods & factory orders", "medium", []),
    27: ("Housing starts & building permits", "medium", ["permits"]),
    91: ("UMich consumer sentiment", "medium", ["umich"]),
    180: ("Weekly jobless claims", "low", []),
}
# Hand-entered reports: (title, rule, region, signal, file)
MANUAL_REPORTS = [
    ("ISM Manufacturing PMI", rel.ISM_MANUFACTURING, "US", "ism_manufacturing", "ism_manufacturing.csv"),
    ("ISM Services PMI", rel.ISM_SERVICES, "US", "ism_services", "ism_services.csv"),
    ("NFIB Small Business Optimism", rel.NFIB, "US", "nfib", "nfib_sbet.csv"),
    ("China NBS official PMIs", rel.NBS, "China", "china", "china_pmi.csv"),
    ("RatingDog China manufacturing PMI", rel.RATINGDOG_MANUFACTURING, "China", "china", "china_pmi.csv"),
    ("RatingDog China services PMI", rel.RATINGDOG_SERVICES, "China", "china", "china_pmi.csv"),
]


BANK_NAMES = {"fomc": "Federal Reserve", "ecb": "ECB", "boj": "Bank of Japan", "boe": "Bank of England"}


@dataclass
class Event:
    date: date
    title: str
    region: str
    category: str  # central_bank | us_data | manual_report
    importance: str  # high | medium | low
    detail: str = ""
    source: str = ""
    url: str | None = None
    signals: tuple[str, ...] = ()

    def to_json(self, today: date) -> dict[str, Any]:
        days = (self.date - today).days
        return {
            "date": self.date.isoformat(),
            "days": days,
            "in_window": WINDOW[0] <= days <= WINDOW[1],
            "title": self.title,
            "region": self.region,
            "category": self.category,
            "importance": self.importance,
            "detail": self.detail,
            "source": self.source,
            "url": self.url,
            "signals": list(self.signals),
        }


def manual_events(start: date, end: date) -> list[Event]:
    out = []
    month = rel.add_months(rel.month_of(start), -2)
    while month <= rel.month_of(end):
        for title, rule, region, signal, file in MANUAL_REPORTS:
            due = rule.due_date(month)
            if start <= due <= end:
                out.append(
                    Event(
                        due,
                        title,
                        region,
                        "manual_report",
                        "high",
                        f"{month} report; you enter it in data/manual/{file}",
                        "Release rule (approximate)",
                        None,
                        (signal,),
                    )
                )
        month = rel.add_months(month, 1)
    return out


def fred_payload(fred: FredClient, start: date) -> dict[str, Any]:
    dates = {}
    for rid in FRED_RELEASES:
        data = fred._get(
            "release/dates",
            release_id=rid,
            include_release_dates_with_no_data="true",
            realtime_start=start.isoformat(),
            realtime_end="9999-12-31",
            sort_order="asc",
            limit=1000,
        )
        dates[str(rid)] = [d["date"] for d in data.get("release_dates", [])]
    if not any(dates.values()):
        raise FetchError("FRED returned no release dates")
    return {"dates": dates}


def fred_events(payload: dict[str, Any]) -> list[Event]:
    out = []
    for rid, days in payload.get("dates", {}).items():
        title, importance, signals = FRED_RELEASES.get(int(rid), (f"FRED release {rid}", "low", []))
        url = f"https://fred.stlouisfed.org/releases/calendar?rid={rid}"
        for d in days:
            out.append(
                Event(
                    date.fromisoformat(d), title, "US", "us_data", importance, "", "FRED", url, tuple(signals)
                )
            )
    return out


def bank_events(bank: str, page: str) -> list[Event]:
    parse, title, region, url = parsers.CENTRAL_BANKS[bank]
    meetings = parse(page)
    if not meetings:
        raise FetchError("no meeting dates found; the page layout may have changed")
    return [
        Event(d, title, region, "central_bank", "high", detail, BANK_NAMES[bank], url)
        for d, detail in meetings
    ]


class CalendarBuilder:
    def __init__(self, cache: RawCache, http: HttpClient, fred: FredClient, *, offline: bool = False) -> None:
        self.cache, self.http, self.fred, self.offline = cache, http, fred, offline
        self.sources: list[dict[str, Any]] = []

    def _source(self, name: str, label: str, fetch, to_events) -> list[Event]:
        status, error, saved_at = "ok", None, iso(utc_now())
        payload = None
        if not self.offline:
            try:
                payload = fetch()
                events = to_events(
                    payload
                )  # parse before saving: never overwrite a good copy with a bad page
                self.cache.save("calendar", name, payload)
            except Exception as exc:  # one broken page must not stop the others
                status, payload = "failed", None
                error = redact(str(exc) if isinstance(exc, FetchError) else f"{type(exc).__name__}: {exc}")
                log.warning("calendar %s: %s", name, error)
        if payload is None:
            hit = self.cache.load("calendar", name)
            if hit is None:
                self.sources.append(
                    {"id": name, "label": label, "status": "missing", "error": error, "events": 0}
                )
                return []
            payload, saved_at = hit
            status = "cached" if status == "ok" else "failed"  # offline -> cached; failed -> using last copy
            try:
                events = to_events(payload)
            except Exception as exc:
                log.warning("calendar %s: cached copy unusable: %s", name, exc)
                events = []
        self.sources.append(
            {
                "id": name,
                "label": label,
                "status": status,
                "error": error,
                "saved_at": saved_at,
                "events": len(events),
            }
        )
        return events

    def build(self, today: date) -> dict[str, Any]:
        start, end = today - timedelta(days=LOOKBACK_DAYS), today + timedelta(days=HORIZON_DAYS)
        events = self._source(
            "fred_releases",
            "US data releases (FRED)",
            lambda: fred_payload(self.fred, start),
            fred_events,
        )
        for bank, (_, title, _, url) in parsers.CENTRAL_BANKS.items():
            events += self._source(
                bank,
                title.replace(" rate decision", "").replace(" policy decision", ""),
                lambda url=url: {"html": self.http.get_page(url)},
                lambda p, bank=bank: bank_events(bank, p["html"]),
            )
        manual = manual_events(start, end)
        events += manual
        self.sources.append(
            {
                "id": "manual",
                "label": "Hand-entered reports (release rules)",
                "status": "ok",
                "error": None,
                "events": len(manual),
            }
        )
        events = sorted((e for e in events if start <= e.date <= end), key=lambda e: (e.date, e.title))
        last_bank = {
            bank: max((e.date for e in events if e.url == url), default=None)
            for bank, (_, _, _, url) in parsers.CENTRAL_BANKS.items()
        }
        return {
            "generated_at": iso(utc_now()),
            "today": today.isoformat(),
            "window": {
                "from": (today + timedelta(days=WINDOW[0])).isoformat(),
                "to": (today + timedelta(days=WINDOW[1])).isoformat(),
                "days": list(WINDOW),
            },
            "events": [e.to_json(today) for e in events],
            "sources": self.sources,
            "covered_until": {k: v.isoformat() if v else None for k, v in last_bank.items()},
        }


def status_of(cal: dict[str, Any]) -> dict[str, Any]:
    """Summary for health.json: ok when every source is fresh."""
    bad = [s for s in cal["sources"] if s["status"] not in ("ok", "cached")]
    return {
        "status": "ok" if not bad else "degraded",
        "events": len(cal["events"]),
        "sources": cal["sources"],
    }
