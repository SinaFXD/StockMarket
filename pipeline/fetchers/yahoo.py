"""Daily prices from Yahoo Finance: ``yfinance`` first, Yahoo's public chart endpoint as a fallback.

Yahoo is unofficial and changes without notice; the fallback keeps the site updating when a
``yfinance`` release breaks. Only completed sessions are stored: a bar for a session still in progress
is dropped, so every stored close is a real close.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from ..config import YAHOO_MIN_INTERVAL_S
from ..http import FetchError, HttpClient
from ..store import SeriesData

log = logging.getLogger(__name__)

CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
START_1900 = -2208988800
META_KEYS = (
    "currency",
    "exchangeName",
    "fullExchangeName",
    "instrumentType",
    "longName",
    "shortName",
    "exchangeTimezoneName",
)


def _epoch(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return int(value)
    try:  # yfinance hands back pandas Timestamps
        return int(value.timestamp())
    except AttributeError:
        return None


def _price(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(num) or num <= 0 else round(num, 4)


def _meta(raw: dict[str, Any]) -> dict[str, Any]:
    meta = {k: raw.get(k) for k in META_KEYS if raw.get(k) is not None}
    regular = (raw.get("currentTradingPeriod") or {}).get("regular") or {}
    meta["session_start"] = _epoch(regular.get("start"))
    meta["session_end"] = _epoch(regular.get("end"))
    return meta


def via_yfinance(symbol: str) -> dict[str, Any]:
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    df = ticker.history(period="max", interval="1d", auto_adjust=False, actions=False, raise_errors=True)
    if df is None or df.empty:
        raise FetchError("yfinance returned no rows")
    adj = df["Adj Close"] if "Adj Close" in df.columns else df["Close"]
    rows = [
        [ts.strftime("%Y-%m-%d"), _price(c), _price(a)]
        for ts, c, a in zip(df.index, df["Close"], adj, strict=True)
    ]
    return {"via": "yfinance", "meta": _meta(ticker.history_metadata or {}), "rows": rows}


def via_chart_api(symbol: str, http: HttpClient, now: float | None = None) -> dict[str, Any]:
    params = {
        "period1": START_1900,
        "period2": int(now or time.time()),
        "interval": "1d",
        "includeAdjustedClose": "true",
        "events": "div,splits",
    }
    data = http.get_json(CHART_URL.format(symbol=quote(symbol, safe="")), params)
    chart = (data or {}).get("chart") or {}
    if chart.get("error"):
        raise FetchError(f"chart API error: {chart['error'].get('description', chart['error'])}")
    try:
        result = chart["result"][0]
        stamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        raise FetchError("chart API returned no price data") from None
    adj = ((result["indicators"].get("adjclose") or [{}])[0]).get("adjclose") or closes
    tz = ZoneInfo(result["meta"].get("exchangeTimezoneName") or "America/New_York")
    rows = [
        [datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d"), _price(c), _price(a)]
        for t, c, a in zip(stamps, closes, adj, strict=False)
    ]
    return {"via": "chart-api", "meta": _meta(result["meta"]), "rows": rows}


def fetch(symbol: str, http: HttpClient | None = None) -> dict[str, Any]:
    try:
        return via_yfinance(symbol)
    except Exception as exc:  # yfinance raises many unrelated types; any failure means "try the fallback"
        first = f"{type(exc).__name__}: {exc}".strip()
        log.warning("yfinance failed for %s (%s); trying the chart API", symbol, first)
    try:
        return via_chart_api(symbol, http or HttpClient(min_interval=YAHOO_MIN_INTERVAL_S))
    except FetchError as exc:
        raise FetchError(f"yfinance: {first[:200]} | chart API: {exc}") from None


def normalize(payload: dict[str, Any], now: float | None = None) -> SeriesData:
    meta = dict(payload.get("meta") or {})
    by_date: dict[str, list[Any]] = {}
    for date, close, adj in payload.get("rows", []):
        if close is not None:
            by_date[date] = [date, close, adj if adj is not None else close]
    rows = [by_date[d] for d in sorted(by_date)]

    start, end, tz = meta.get("session_start"), meta.get("session_end"), meta.get("exchangeTimezoneName")
    if rows and start and end and tz and (now or time.time()) < end:
        session_day = datetime.fromtimestamp(start, ZoneInfo(tz)).strftime("%Y-%m-%d")
        if rows[-1][0] == session_day:
            rows.pop()  # session still trading: not a close yet
    if not rows:
        raise FetchError("no completed daily closes")
    out_meta = {
        "title": meta.get("longName") or meta.get("shortName"),
        "units": meta.get("currency"),
        "units_short": meta.get("currency"),
        "frequency": "daily",
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "via": payload.get("via"),
    }
    return SeriesData(meta=out_meta, columns=["date", "close", "adj_close"], rows=rows)
