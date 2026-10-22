"""One trade-idea page per stock (``site/data/stocks/<T>.json``): the template's sections 1-5 filled with what
the data can fill (lesson 33). The screener row (``stocks.json``) carries the 11 numbers, the type and the
volatility; this file adds what only the stock page needs.

1. Quant table: EPS and sales (reported, current and next fiscal year with the analysts' range), shares, GAAP
   net income from the SEC, the story comment and the default price targets.
2. Sector comparison and volatility: from ``stocks.json`` on the page; here the daily bars for the return
   distribution.
3. Qualitative: Yahoo's company profile, ownership, analysts' ratings and price targets.
4. Earnings: next date, before the open or after the close, quarter and annual expectations with the range.
5. Timing: one year of daily bars, moving averages, 52-week range, relative strength, short interest.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from . import targets

ET = ZoneInfo("America/New_York")
# Yahoo sector -> the SPDR sector ETF used for relative strength (series published by the pipeline)
SECTOR_ETF = {
    "Basic Materials": "XLB",
    "Communication Services": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Industrials": "XLI",
    "Real Estate": "XLRE",
    "Technology": "XLK",
    "Utilities": "XLU",
}


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def earnings_time(ts: Any, estimated: Any) -> dict[str, Any] | None:
    """Next earnings date and session. Yahoo keeps report times at a fixed UTC hour (an after-the-close report
    shows 15:00 or 16:00 New York time), so the session is read from the hour; an estimated date has no time."""
    v = _num(ts)
    if not v:
        return None
    t = datetime.fromtimestamp(v, tz=UTC).astimezone(ET)
    if estimated:
        session = "date estimated, time not confirmed"
    elif t.hour * 60 + t.minute < 9 * 60 + 30:
        session = "before the open"
    elif t.hour >= 14:
        session = "after the close"
    else:
        session = "during market hours"
    return {"date": t.date().isoformat(), "session": session, "estimated": bool(estimated)}


def _ma(closes: list[float], n: int) -> float | None:
    return mean(closes[-n:]) if len(closes) >= n else None


def technicals(
    bars: dict[str, list] | None, etf_returns: dict[str, float | None], sector: str | None
) -> dict:
    """Moving averages, 52-week range, returns and relative strength (lesson 33, section 5: price action)."""
    closes = [c for c in (bars or {}).get("c", []) if c is not None]
    if len(closes) < 30:
        return {}
    last = closes[-1]
    highs = [h for h in bars.get("h", []) if h is not None] or closes
    lows = [lo for lo in bars.get("l", []) if lo is not None] or closes
    ma50, ma200 = _ma(closes, 50), _ma(closes, 200)
    out: dict[str, Any] = {
        "last": last,
        "date": bars["d"][-1],
        "ma20": _ma(closes, 20),
        "ma50": ma50,
        "ma200": ma200,
        "high52": max(highs[-252:]),
        "low52": min(lows[-252:]),
        "r1m": targets.period_return(closes, 21),
        "r3m": targets.period_return(closes, 63),
        "r6m": targets.period_return(closes, 126),
    }
    out["off_high"] = (last / out["high52"] - 1) * 100 if out["high52"] else None
    etf = SECTOR_ETF.get(sector or "")
    if out["r3m"] is not None:
        if etf_returns.get("SPY") is not None:
            out["rs_spy_3m"] = out["r3m"] - etf_returns["SPY"]
        if etf and etf_returns.get(etf) is not None:
            out["rs_sector_3m"] = out["r3m"] - etf_returns[etf]
            out["sector_etf"] = etf
    out["reading"] = trend_reading(last, ma50, ma200)
    return out


def trend_reading(last: float, ma50: float | None, ma200: float | None) -> str:
    if ma50 is None:
        return "Not enough history for the moving averages."
    if ma200 is None:
        return (
            f"Price {'above' if last > ma50 else 'below'} its 50-day average (less than 200 days of history)."
        )
    if last > ma50 > ma200:
        return "Uptrend: price above the 50-day average, which is above the 200-day."
    if last < ma50 < ma200:
        return "Downtrend: price below the 50-day average, which is below the 200-day."
    if ma50 > ma200:
        return "Pullback in an uptrend: price below the 50-day average, the 50-day still above the 200-day."
    return "Rebound in a downtrend: price above the 50-day average, the 50-day still below the 200-day."


def short_interest(stats: dict[str, Any], p: dict) -> dict[str, Any] | None:
    """Short interest as the path-of-least-resistance check (lesson 33, section 5)."""
    pct = _num(stats.get("short_pct_float"))
    days = _num(stats.get("short_ratio"))
    now, prior = _num(stats.get("shares_short")), _num(stats.get("shares_short_prior"))
    if pct is None and days is None and now is None:
        return None
    change = (now / prior - 1) * 100 if now is not None and prior else None
    crowded = (pct is not None and pct * 100 >= p["short_crowded_pct"]) or (
        days is not None and days >= p["short_crowded_days"]
    )
    parts = []
    if pct is not None:
        parts.append(f"{pct * 100:.1f}% of the float is sold short")
    if days is not None:
        parts.append(f"{days:.1f} days to cover")
    if change is not None and abs(change) >= p["short_change_pct"]:
        parts.append(f"{'up' if change > 0 else 'down'} {abs(change):.0f}% on the prior month")
    text = ", ".join(parts) + "."
    text = text[0].upper() + text[1:]
    if crowded:
        text += (
            " A crowded short: for a long, a squeeze can add fuel; for a short, it is a crowded trade with squeeze"
            " risk."
        )
    else:
        text += " Not a crowded short."
    return {
        "pct_float": pct * 100 if pct is not None else None,
        "days_to_cover": days,
        "shares_short": now,
        "change_pct": change,
        "date": stats.get("short_date"),
        "crowded": crowded,
        "text": text,
    }


def _fy_label(end: str | None, offset: int = 0) -> str | None:
    return f"FY{int(end[:4]) + offset}" if end else None


def build(
    row: dict[str, Any],
    quote: dict[str, Any],
    summary: dict[str, Any] | None,
    bars: dict[str, list] | None,
    acc: dict[str, Any] | None,
    etf_returns: dict[str, float | None],
    p: dict,
    as_of: str,
) -> dict[str, Any]:
    s = summary or {}
    y0, y1, q0 = s.get("0y") or {}, s.get("+1y") or {}, s.get("0q") or {}
    stats = s.get("stats") or {}
    shares = _num(stats.get("shares")) or _num(quote.get("sharesOutstanding"))
    if not shares and row.get("mcap") and row.get("price"):
        shares = row["mcap"] / row["price"]
    end1 = y0.get("end")
    quant = {
        "labels": [_fy_label(end1, -1), _fy_label(end1), _fy_label(y1.get("end"))],
        "ends": [None, end1, y1.get("end")],
        "eps": [row.get("eps0"), row.get("eps1"), row.get("eps2")],
        "eps_low": [None, y0.get("eps_low"), y1.get("eps_low")],
        "eps_high": [None, y0.get("eps_high"), y1.get("eps_high")],
        "analysts": [None, y0.get("analysts"), y1.get("analysts")],
        "sales": [_num(y0.get("rev_year_ago")), _num(y0.get("rev")), _num(y1.get("rev"))],
        "sales_low": [None, y0.get("rev_low"), y1.get("rev_low")],
        "sales_high": [None, y0.get("rev_high"), y1.get("rev_high")],
        "revisions": [
            None,
            {
                "up": y0.get("revisions_up_30d"),
                "down": y0.get("revisions_down_30d"),
                "eps_90d": y0.get("eps_90d_ago"),
            },
            {
                "up": y1.get("revisions_up_30d"),
                "down": y1.get("revisions_down_30d"),
                "eps_90d": y1.get("eps_90d_ago"),
            },
        ],
        "shares": shares,
    }
    gaap = None
    if acc and acc.get("fy_end") and end1:
        # the SEC year must be the one before the current fiscal year (FY0), within 40 days
        fy0_end = date(int(end1[:4]) - 1, int(end1[5:7]), min(int(end1[8:10]), 28))
        if abs((date.fromisoformat(acc["fy_end"]) - fy0_end).days) <= 40:
            gaap = {
                "fy_end": acc["fy_end"],
                "net_income": acc.get("net_income"),
                "revenue": acc.get("revenue"),
            }
            gap = targets.gaap_gap(row.get("eps0"), shares, acc.get("net_income"), p)
            if gap:
                gaap.update(gap)
    vol = row.get("iv") or row.get("rv")
    horizon = p["horizon_days"]
    default_targets = targets.price_targets(row.get("price"), quant["eps"], quant["sales"], shares)
    sig = targets.sigma_move(vol, horizon)
    for y in default_targets["years"]:
        y["eps_realism"] = targets.realism(y["eps_move"], sig, p)
        y["sales_realism"] = targets.realism(y["sales_move"], sig, p)
    profile = s.get("profile") or {}
    return {
        "t": row["t"],
        "as_of": as_of,
        "profile": {**profile, "country": s.get("country")},
        "quant": quant,
        "gaap": gaap,
        "story": targets.story(row, p),
        "targets": {**default_targets, "vol": vol, "vol_source": "implied" if row.get("iv") else "realised"},
        "sigma": {str(d): targets.sigma_move(vol, d) for d in (30, 60, 90)},
        "quarter": {
            "end": q0.get("end"),
            "eps": q0.get("eps"),
            "eps_low": q0.get("eps_low"),
            "eps_high": q0.get("eps_high"),
            "eps_year_ago": q0.get("eps_year_ago"),
            "analysts": q0.get("analysts"),
            "rev": q0.get("rev"),
            "rev_low": q0.get("rev_low"),
            "rev_high": q0.get("rev_high"),
            "rev_year_ago": q0.get("rev_year_ago"),
        }
        if q0
        else None,
        "earnings": earnings_time(
            s.get("earnings_date") or quote.get("earningsTimestamp"), s.get("earnings_date_estimated")
        ),
        "analysts": s.get("analysts"),
        "ownership": {
            "insiders": stats.get("insiders"),
            "institutions": stats.get("institutions"),
            "beta": stats.get("beta"),
        },
        "short": short_interest(stats, p),
        "technicals": technicals(bars, etf_returns, row.get("sector")),
        "prices": bars,
    }
