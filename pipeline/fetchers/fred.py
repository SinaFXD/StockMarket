"""FRED observations and ALFRED real-time vintages (both served by api.stlouisfed.org).

ALFRED rows are ``[date, realtime_start, realtime_end, value]``: the value of observation ``date`` as
published from ``realtime_start`` to ``realtime_end`` (inclusive). That is enough to rebuild the series
exactly as it was known on any past day (:func:`as_known_on`) or to take each observation's first
release (:func:`first_release`), so backtests only use data that existed at the time.
"""

from __future__ import annotations

from typing import Any

from ..config import FRED_MIN_INTERVAL_S
from ..http import FetchError, HttpClient
from ..store import SeriesData

BASE_URL = "https://api.stlouisfed.org/fred/"
EARLIEST = "1776-07-04"  # ALFRED's documented "all vintages" bounds
LATEST = "9999-12-31"
PAGE_LIMIT = 100_000
FREQUENCIES = {
    "D": "daily",
    "W": "weekly",
    "BW": "biweekly",
    "M": "monthly",
    "Q": "quarterly",
    "SA": "semiannual",
    "A": "annual",
}
MISSING = {".", "", None}


class FredClient:
    def __init__(self, api_key: str | None, http: HttpClient | None = None) -> None:
        self.api_key = api_key or None
        self.http = http or HttpClient(min_interval=FRED_MIN_INTERVAL_S, secrets=[api_key or ""])

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        if not self.api_key:
            raise FetchError("FRED_API_KEY is not set (add it as a repository secret, see docs/06-setup.md)")
        params.update(api_key=self.api_key, file_type="json")
        data = self.http.get_json(BASE_URL + path, params)
        if not isinstance(data, dict):
            raise FetchError(f"unexpected FRED response for {path}")
        return data

    def series_info(self, series_id: str) -> dict[str, Any]:
        data = self._get("series", series_id=series_id)
        try:
            return data["seriess"][0]
        except (KeyError, IndexError):
            raise FetchError(f"FRED returned no metadata for {series_id}") from None

    def _paged(self, series_id: str, **params: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        while True:
            data = self._get(
                "series/observations", series_id=series_id, limit=PAGE_LIMIT, offset=len(out), **params
            )
            page = data.get("observations")
            if not isinstance(page, list):
                raise FetchError(f"FRED returned no observations for {series_id}")
            out.extend(page)
            if not page or len(out) >= int(data.get("count", 0)):
                return out

    def observations(self, series_id: str) -> list[list[str]]:
        return [[o["date"], o["value"]] for o in self._paged(series_id)]

    def vintages(self, series_id: str) -> list[list[str]]:
        rows = self._paged(series_id, realtime_start=EARLIEST, realtime_end=LATEST)
        return [[o["date"], o["realtime_start"], o["realtime_end"], o["value"]] for o in rows]


def fetch(client: FredClient, series_id: str, cached: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    """Return ``(payload, reused)``. Observations are only downloaded when FRED's ``last_updated`` changed."""
    info = client.series_info(series_id)
    if (
        cached
        and cached.get("observations")
        and cached.get("series", {}).get("last_updated") == info.get("last_updated")
    ):
        return {"series": info, "observations": cached["observations"]}, True
    return {"series": info, "observations": client.observations(series_id)}, False


def fetch_vintages(
    client: FredClient, series_id: str, last_updated: str | None, cached: dict[str, Any] | None
) -> tuple[dict[str, Any], bool]:
    if cached and cached.get("rows") and last_updated and cached.get("last_updated") == last_updated:
        return cached, True
    rows = client.vintages(series_id)
    if not rows:
        raise FetchError(f"ALFRED returned no vintages for {series_id}")
    return {"last_updated": last_updated, "rows": rows}, False


def _number(value: str) -> float | int | None:
    if value in MISSING:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return int(num) if num.is_integer() and "." not in value and "e" not in value.lower() else num


def normalize(payload: dict[str, Any]) -> SeriesData:
    info = payload.get("series") or {}
    rows = [[d, v] for d, raw in payload.get("observations", []) if (v := _number(raw)) is not None]
    if not rows:
        raise FetchError("no numeric observations")
    rows.sort(key=lambda r: r[0])
    freq = info.get("frequency_short", "")
    meta = {
        "title": info.get("title"),
        "units": info.get("units"),
        "units_short": info.get("units_short"),
        "frequency": FREQUENCIES.get(freq, (info.get("frequency") or "unknown").lower()),
        "seasonal_adjustment": info.get("seasonal_adjustment_short"),
        "source_updated": info.get("last_updated"),
    }
    return SeriesData(meta=meta, columns=["date", "value"], rows=rows)


def as_known_on(rows: list[list[str]], day: str) -> list[list[Any]]:
    """The series as it was published on ``day`` (ISO date): ``[[date, value], ...]``."""
    out = [[d, v] for d, start, end, raw in rows if start <= day <= end and (v := _number(raw)) is not None]
    return sorted(out, key=lambda r: r[0])


def first_release(rows: list[list[str]]) -> list[list[Any]]:
    """Each observation's first published value: ``[[date, value, release_date], ...]``."""
    first: dict[str, list[Any]] = {}
    for d, start, _end, raw in rows:
        v = _number(raw)
        if v is not None and (d not in first or start < first[d][2]):
            first[d] = [d, v, start]
    return [first[d] for d in sorted(first)]
