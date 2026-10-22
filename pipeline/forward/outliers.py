"""Forward test of the Screener's types (lessons 25-27): do positive outliers beat negative outliers over the next
20, 40 and 60 trading days?

There is no free point-in-time history of analysts' estimates, so the types cannot be backtested honestly (today's
estimates would leak into the past, and stocks that disappeared would be missing). Instead the pipeline keeps a
live record from now on:

- once per ISO week (the first run whose last close falls in a new week) every stock of a candidate type is
  written down with its type, sector, volatility filter and closing price: a **cohort**;
- every run fills in, for each row old enough, the return over 20 / 40 / 60 trading days (counted on SPY's
  trading days) of the stock, of SPY and of the stock's SPDR sector ETF. A stock that left the screener's universe
  is priced from a separate download; a stock with no price at all keeps an empty cell (reported, never guessed).

A second, pre-registered test (added 2026-10-22, before the first cohort) asks whether **estimate revisions** do
better than **forecast growth levels**: within each sector, the quarter of stocks whose EPS1 consensus rose most in
90 days ("up") and the quarter where it fell most ("down") are written down too. Hypotheses, fixed in advance
(``docs/12-track-record.md``): H1, "up" beats "down"; H2, positive outliers with rising estimates beat the other
positive outliers. Both spreads are reported next to the types' spread, whatever they show.

The record is ``site/data/forward/outliers.csv`` (committed by the workflow, like ``macro/log.csv``); the results
are ``summary.json``. Context only: nothing here changes a rule. Never tune the types to this record.
"""

from __future__ import annotations

import csv
import io
import math
from datetime import date
from statistics import mean, stdev
from typing import Any

CANDIDATES = ("positive", "negative", "post_growth", "turnaround", "value_trap")
LONG_TYPES = ("positive",)
SHORT_TYPES = ("negative", "post_growth")
HORIZONS = (20, 40, 60)
RETURNS = [f"{k}{h}" for h in HORIZONS for k in ("r", "spy", "etf")]
FIELDS = ["cohort", "ticker", "type", "sector", "vol_ok", "entry", *RETURNS, "rev90", "rev_group"]
REV_GROUPS = ("up", "down")
REV_QUARTER = 0.25  # top / bottom quarter of the sector's 90-day EPS1 revisions
REV_MIN_STOCKS = 8  # fewer stocks with a revision in a sector: no revision groups there


def week_of(day: str) -> tuple[int, int]:
    y, w, _ = date.fromisoformat(day).isocalendar()
    return y, w


def read(text: str) -> list[dict[str, Any]]:
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        out: dict[str, Any] = {
            "cohort": r["cohort"],
            "ticker": r["ticker"],
            "type": r["type"],
            "sector": r["sector"],
        }
        out["vol_ok"] = {"1": True, "0": False}.get(r.get("vol_ok", ""), None)
        for k in ["entry", *RETURNS, "rev90"]:
            v = r.get(k, "")
            out[k] = float(v) if v not in ("", None) else None
        out["rev_group"] = r.get("rev_group") or None
        rows.append(out)
    return rows


def write(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(FIELDS)
    for r in rows:
        vals = []
        for k in FIELDS:
            v = r.get(k)
            if k == "vol_ok":
                vals.append("" if v is None else "1" if v else "0")
            elif isinstance(v, float):
                vals.append(f"{v:.4f}" if k == "entry" else f"{v:.3f}")
            else:
                vals.append("" if v is None else v)
        w.writerow(vals)
    return buf.getvalue()


def revision_groups(screener_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Ticker -> "up" / "down": the top and bottom quarter of each sector's 90-day EPS1 revisions."""
    by_sector: dict[str, list[tuple[float, str]]] = {}
    for r in screener_rows:
        v = r.get("eps1_rev90")
        if v is not None and r.get("sector"):
            by_sector.setdefault(r["sector"], []).append((float(v), r["t"]))
    out: dict[str, str] = {}
    for items in by_sector.values():
        if len(items) < REV_MIN_STOCKS:
            continue
        items.sort()
        k = max(1, int(len(items) * REV_QUARTER))
        lo, hi = items[k - 1][0], items[-k][0]
        for v, t in items:
            if v >= hi and v > lo:
                out[t] = "up"
            elif v <= lo and v < hi:
                out[t] = "down"
    return out


def add_cohort(log: list[dict[str, Any]], day: str, screener_rows: list[dict[str, Any]], closes) -> int:
    """Append this week's cohort unless the log already has one for the ISO week of ``day``: every stock of a
    candidate type or of a revision group. ``closes(t)`` gives the stock's ``{date: close}``; the entry is the close
    on ``day``. Returns the number of rows added."""
    if any(week_of(r["cohort"]) == week_of(day) for r in log):
        return 0
    groups = revision_groups(screener_rows)
    added = 0
    for r in screener_rows:
        if r.get("cls") not in CANDIDATES and r["t"] not in groups:
            continue
        entry = (closes(r["t"]) or {}).get(day)
        if not entry:
            continue
        row = {
            "cohort": day,
            "ticker": r["t"],
            "type": r["cls"],
            "sector": r.get("sector") or "",
            "vol_ok": r.get("vol_ok"),
        }
        row["entry"] = float(entry)
        for k in RETURNS:
            row[k] = None
        row["rev90"] = r.get("eps1_rev90")
        row["rev_group"] = groups.get(r["t"])
        log.append(row)
        added += 1
    return added


def _close_on(series: dict[str, float], day: str) -> float | None:
    """Close on ``day``, or the last close before it within 5 days (a halt or a holiday)."""
    if day in series:
        return series[day]
    earlier = [d for d in series if d < day]
    if not earlier:
        return None
    last = max(earlier)
    return series[last] if (date.fromisoformat(day) - date.fromisoformat(last)).days <= 5 else None


def fill(
    log: list[dict[str, Any]],
    trading_days: list[str],
    closes,
    spy: dict[str, float],
    etfs: dict[str, dict],
    etf_of,
) -> int:
    """Fill the returns of every row whose horizon has passed. ``trading_days``: SPY's dates (sorted)."""
    index = {d: i for i, d in enumerate(trading_days)}
    filled = 0
    for r in log:
        i0 = index.get(r["cohort"])
        if i0 is None:
            continue
        for h in HORIZONS:
            if r[f"r{h}"] is not None or i0 + h >= len(trading_days):
                continue
            end = trading_days[i0 + h]
            stock = _close_on(closes(r["ticker"]) or {}, end)
            if stock is None:
                continue
            r[f"r{h}"] = (stock / r["entry"] - 1) * 100
            s0, s1 = _close_on(spy, r["cohort"]), _close_on(spy, end)
            r[f"spy{h}"] = (s1 / s0 - 1) * 100 if s0 and s1 else None
            etf = etfs.get(etf_of(r["sector"]) or "") or {}
            e0, e1 = _close_on(etf, r["cohort"]), _close_on(etf, end)
            r[f"etf{h}"] = (e1 / e0 - 1) * 100 if e0 and e1 else None
            filled += 1
    return filled


def due_tickers(log: list[dict[str, Any]], trading_days: list[str], have) -> list[str]:
    """Tickers with a horizon due and no price in the screener's bars (they left the universe)."""
    index = {d: i for i, d in enumerate(trading_days)}
    out = set()
    for r in log:
        i0 = index.get(r["cohort"])
        if i0 is None or have(r["ticker"]):
            continue
        if any(r[f"r{h}"] is None and i0 + h < len(trading_days) for h in HORIZONS):
            out.add(r["ticker"])
    return sorted(out)


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "pct_pos": None}
    s = sorted(values)
    mid = len(s) // 2
    return {
        "n": len(s),
        "mean": round(mean(s), 3),
        "median": round(s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2, 3),
        "pct_pos": round(100 * sum(1 for v in s if v > 0) / len(s), 1),
    }


def summary(log: list[dict[str, Any]], vol_only: bool = False) -> dict[str, Any]:
    """Per horizon: each type's raw return and excess over SPY and over its sector ETF; and the long-short
    spread (positive minus negative outliers) per cohort, with its t-statistic and the number of independent
    windows (weekly cohorts overlap when the horizon is longer than a week)."""
    rows = [r for r in log if not vol_only or r["vol_ok"] is True]
    out: dict[str, Any] = {"cohorts": len({r["cohort"] for r in rows}), "rows": len(rows), "horizons": {}}
    for h in HORIZONS:
        done = [r for r in rows if r[f"r{h}"] is not None]
        types = {}
        for t in CANDIDATES:
            mine = [r for r in done if r["type"] == t]
            types[t] = {
                "return": _stats([r[f"r{h}"] for r in mine]),
                "vs_spy": _stats([r[f"r{h}"] - r[f"spy{h}"] for r in mine if r[f"spy{h}"] is not None]),
                "vs_sector": _stats([r[f"r{h}"] - r[f"etf{h}"] for r in mine if r[f"etf{h}"] is not None]),
                "cohorts": len({r["cohort"] for r in mine}),
            }
        revisions = {}
        for g in REV_GROUPS:
            mine = [r for r in done if r.get("rev_group") == g]
            revisions[g] = {
                "return": _stats([r[f"r{h}"] for r in mine]),
                "vs_spy": _stats([r[f"r{h}"] - r[f"spy{h}"] for r in mine if r[f"spy{h}"] is not None]),
                "vs_sector": _stats([r[f"r{h}"] - r[f"etf{h}"] for r in mine if r[f"etf{h}"] is not None]),
                "cohorts": len({r["cohort"] for r in mine}),
            }
        out["horizons"][str(h)] = {
            "types": types,
            # the types' test: positive outliers minus negative outliers
            "spread": _spread(done, h, lambda r: r["type"] == "positive", lambda r: r["type"] == "negative"),
            "revisions": revisions,
            # H1: rising estimates minus falling estimates
            "rev_spread": _spread(
                done, h, lambda r: r.get("rev_group") == "up", lambda r: r.get("rev_group") == "down"
            ),
            # H2: positive outliers whose estimates are rising minus the other positive outliers
            "positive_rev_spread": _spread(
                done,
                h,
                lambda r: r["type"] == "positive" and r.get("rev_group") == "up",
                lambda r: r["type"] == "positive" and r.get("rev_group") != "up",
            ),
        }
    return out


def _spread(done: list[dict[str, Any]], h: int, long, short) -> dict[str, Any]:
    """Mean of ``long`` minus mean of ``short`` within each cohort, with its t-statistic."""
    spreads = []
    for c in sorted({r["cohort"] for r in done}):
        a = [r[f"r{h}"] for r in done if r["cohort"] == c and long(r)]
        b = [r[f"r{h}"] for r in done if r["cohort"] == c and short(r)]
        if a and b:
            spreads.append(mean(a) - mean(b))
    n = len(spreads)
    sd = stdev(spreads) if n >= 2 else None
    # weekly cohorts overlap when the horizon is longer than 5 trading days: the t-statistic uses the number of
    # independent windows, not the number of cohorts, so it is not overstated
    n_ind = n * 5 / h
    return {
        "n_cohorts": n,
        "n_independent": round(n_ind, 1),
        "mean": round(mean(spreads), 3) if spreads else None,
        "t": round(mean(spreads) / (sd / math.sqrt(n_ind)), 2) if sd and n_ind >= 2 else None,
        "pct_pos": round(100 * sum(1 for s in spreads if s > 0) / n, 1) if n else None,
    }
