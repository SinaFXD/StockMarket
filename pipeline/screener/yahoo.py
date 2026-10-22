"""Yahoo Finance for the Sector Screener: the universe (Yahoo's equity screener, one query per sector) and each
stock's forward estimates (``quoteSummary``: earnings and revenue estimates, profile, next earnings date).

Yahoo is unofficial: both calls go through ``yfinance`` (which handles Yahoo's cookie/crumb) and every
result is cached, so a failed day keeps the last good copy.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ..http import FetchError

# Yahoo's sector names (its screener's "sector" field)
SECTORS = [
    "Basic Materials",
    "Communication Services",
    "Consumer Cyclical",
    "Consumer Defensive",
    "Energy",
    "Financial Services",
    "Healthcare",
    "Industrials",
    "Real Estate",
    "Technology",
    "Utilities",
]
# NYSE, Nasdaq (global select / global / capital market), NYSE American
EXCHANGES = ["NYQ", "NMS", "NGM", "NCM", "ASE"]
QUOTE_FIELDS = [
    "symbol",
    "longName",
    "shortName",
    "exchange",
    "quoteType",
    "currency",
    "financialCurrency",
    "regularMarketPrice",
    "regularMarketTime",
    "marketCap",
    "sharesOutstanding",
    "averageDailyVolume3Month",
    "epsTrailingTwelveMonths",
    "epsCurrentYear",
    "epsForward",
    "fiftyTwoWeekHigh",
    "fiftyTwoWeekLow",
    "twoHundredDayAverage",
    "earningsTimestamp",
]
SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
SUMMARY_MODULES = "earningsTrend,assetProfile,calendarEvents,price,defaultKeyStatistics,financialData"
PAGE = 250
# preferred shares, warrants, units and rights are not common stock (e.g. BAC-PL, XYZ-WT)
NOT_COMMON = re.compile(r"-(P[A-Z]{0,2}|WT|WS|U|UN|RT)$")


def default_screen() -> Callable[..., dict[str, Any]]:
    import yfinance as yf

    def screen(sector: str, min_cap: float, offset: int) -> dict[str, Any]:
        q = yf.EquityQuery(
            "and",
            [
                yf.EquityQuery("eq", ["region", "us"]),
                yf.EquityQuery("eq", ["sector", sector]),
                yf.EquityQuery("gt", ["intradaymarketcap", min_cap]),
                yf.EquityQuery("is-in", ["exchange", *EXCHANGES]),
            ],
        )
        return yf.screen(q, offset=offset, size=PAGE, sortField="intradaymarketcap", sortAsc=False)

    return screen


def default_get_json() -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    from yfinance.data import YfData

    data = YfData()
    return lambda url, params: data.get_raw_json(url, params=params)


def fetch_universe(min_cap: float, screen: Callable[..., dict[str, Any]]) -> list[dict[str, Any]]:
    """Every US-listed equity above ``min_cap``, tagged with its sector, largest first within each sector."""
    out: list[dict[str, Any]] = []
    for sector in SECTORS:
        offset, total = 0, None
        while total is None or offset < total:
            res = screen(sector, min_cap, offset)
            quotes = res.get("quotes") or []
            total = int(res.get("total") or 0)
            for q in quotes:
                if q.get("quoteType", "EQUITY") != "EQUITY" or NOT_COMMON.search(q.get("symbol") or ""):
                    continue
                out.append({**{k: q.get(k) for k in QUOTE_FIELDS}, "sector": sector})
            if not quotes:
                break
            offset += len(quotes)
    if not out:
        raise FetchError("the Yahoo screener returned no stocks")
    return out


def _raw(v: Any) -> Any:
    return v.get("raw") if isinstance(v, dict) else v


def _date(ts: Any) -> str | None:
    v = _raw(ts)
    try:
        return datetime.fromtimestamp(float(v), tz=UTC).date().isoformat() if v else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def trim_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Keep only what the screener and the trade-idea pages use."""
    profile = result.get("assetProfile") or {}
    price = result.get("price") or {}
    stats = result.get("defaultKeyStatistics") or {}
    fin = result.get("financialData") or {}
    trend = {t.get("period"): t for t in (result.get("earningsTrend") or {}).get("trend", [])}
    out: dict[str, Any] = {
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "country": profile.get("country"),
        "currency": price.get("currency"),
        "quote_type": price.get("quoteType"),
        # trade-idea template (lessons 30-33): profile, ownership, short interest, analysts' price targets
        "profile": {
            "summary": (profile.get("longBusinessSummary") or "")[:2000] or None,
            "employees": _raw(profile.get("fullTimeEmployees")),
            "website": profile.get("website"),
            "city": profile.get("city"),
            "state": profile.get("state"),
        },
        "stats": {
            "shares": _raw(stats.get("sharesOutstanding")) or _raw(stats.get("impliedSharesOutstanding")),
            "float_shares": _raw(stats.get("floatShares")),
            "shares_short": _raw(stats.get("sharesShort")),
            "shares_short_prior": _raw(stats.get("sharesShortPriorMonth")),
            "short_date": _date(stats.get("dateShortInterest")),
            "short_prior_date": _date(stats.get("sharesShortPreviousMonthDate")),
            "short_pct_float": _raw(stats.get("shortPercentOfFloat")),
            "short_ratio": _raw(stats.get("shortRatio")),
            "insiders": _raw(stats.get("heldPercentInsiders")),
            "institutions": _raw(stats.get("heldPercentInstitutions")),
            "beta": _raw(stats.get("beta")),
        },
        "analysts": {
            "target_low": _raw(fin.get("targetLowPrice")),
            "target_mean": _raw(fin.get("targetMeanPrice")),
            "target_median": _raw(fin.get("targetMedianPrice")),
            "target_high": _raw(fin.get("targetHighPrice")),
            "rec_mean": _raw(fin.get("recommendationMean")),
            "rec_key": fin.get("recommendationKey"),
            "opinions": _raw(fin.get("numberOfAnalystOpinions")),
        },
    }
    for period in ("0q", "0y", "+1y"):
        t = trend.get(period) or {}
        eps = t.get("earningsEstimate") or {}
        rev = t.get("revenueEstimate") or {}
        eps_trend = t.get("epsTrend") or {}
        revisions = t.get("epsRevisions") or {}
        out[period] = {
            "end": t.get("endDate"),
            "eps": _raw(eps.get("avg")),
            "eps_low": _raw(eps.get("low")),
            "eps_high": _raw(eps.get("high")),
            "eps_year_ago": _raw(eps.get("yearAgoEps")),
            "analysts": _raw(eps.get("numberOfAnalysts")),
            "eps_currency": eps.get("earningsCurrency"),
            "eps_90d_ago": _raw(eps_trend.get("90daysAgo")),
            "revisions_up_30d": _raw(revisions.get("upLast30days")),
            "revisions_down_30d": _raw(revisions.get("downLast30days")),
            "rev": _raw(rev.get("avg")),
            "rev_low": _raw(rev.get("low")),
            "rev_high": _raw(rev.get("high")),
            "rev_year_ago": _raw(rev.get("yearAgoRevenue")),
            "rev_analysts": _raw(rev.get("numberOfAnalysts")),
        }
    earnings = (result.get("calendarEvents") or {}).get("earnings") or {}
    dates = earnings.get("earningsDate") or []
    out["earnings_date"] = _raw(dates[0]) if dates else None
    out["earnings_date_estimated"] = earnings.get("isEarningsDateEstimate")
    return out


def fetch_summary(symbol: str, get_json: Callable[[str, dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    body = get_json(SUMMARY_URL.format(symbol=symbol), {"modules": SUMMARY_MODULES, "formatted": "false"})
    qs = (body or {}).get("quoteSummary") or {}
    if qs.get("error"):
        raise FetchError(str((qs["error"] or {}).get("description") or qs["error"])[:200])
    results = qs.get("result") or []
    if not results:
        raise FetchError(f"no quoteSummary for {symbol}")
    return trim_summary(results[0])
