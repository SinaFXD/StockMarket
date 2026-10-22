"""The Evidence page (``site/data/macro/evidence.json``): what happened to equity markets after each bias reading.

Honest by construction (docs/02 "Combining", CLAUDE.md "Honest backtests"):
- the bias at each month-end comes from the point-in-time snapshots (ALFRED vintages, release calendars,
  prices up to that day), never from today's revised data where a real-time vintage exists;
- the rules and thresholds were written from the lessons before these numbers were computed, and nothing is fitted
  to them: this page reports, it does not tune;
- every figure comes with its sample size; overlapping windows are flagged (a 6-month return starts every month,
  so neighbouring samples share most of their path);
- months that needed revised data are counted, and a "real-time inputs only" view excludes them.
Returns are price returns in each index's own currency, from month-end close to month-end close.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .base import value_at
from .charts import line, panel
from .data import View

ASSETS = [
    ("sp500", "S&P 500", "yahoo/GSPC"),
    ("stoxx", "STOXX Europe 600", "yahoo/STOXX"),
    ("nikkei", "Nikkei 225", "yahoo/N225"),
    ("shanghai", "Shanghai Composite", "yahoo/000001_SS"),
    ("acwi", "All-world (ACWI ETF, USD)", "yahoo/ACWI"),
]
HORIZONS = {"1m": 1, "3m": 3, "6m": 6}
STATES = [("net_long", "Net long"), ("neutral", "Neutral"), ("net_short", "Net short")]
PERIODS = [
    ("all", "All months"),
    ("2000-2012", "2000-2012"),
    ("2013-now", "2013 to now"),
    ("realtime", "Real-time inputs only"),
]


def month_end(month: str) -> pd.Timestamp:
    return pd.Timestamp(f"{month}-01") + pd.offsets.MonthEnd(0)


def forward_return(prices: pd.Series, start: pd.Timestamp, months: int) -> float | None:
    """Close on the last trading day <= start, to the last trading day <= the month-end ``months`` later."""
    if prices.empty:
        return None
    end = start + pd.offsets.MonthEnd(months)
    if end > prices.index[-1] or start < prices.index[0]:
        return None
    p0, p1 = value_at(prices, start), value_at(prices, end)
    if not p0 or p1 is None:
        return None
    return (p1 / p0 - 1) * 100


def stats(values: list[float], months: int) -> dict[str, Any]:
    arr = np.array([v for v in values if v is not None], dtype=float)
    n = int(arr.size)
    if n == 0:
        return {"n": 0}
    return {
        "n": n,
        "n_independent": max(1, n // months),  # roughly how many non-overlapping windows the sample holds
        "mean": round(float(arr.mean()), 2),
        "median": round(float(np.median(arr)), 2),
        "pct_up": round(float((arr > 0).mean() * 100), 1),
        "worst": round(float(arr.min()), 2),
        "best": round(float(arr.max()), 2),
    }


def _in_period(month: str, revised: bool, period: str) -> bool:
    if period == "2000-2012":
        return month <= "2012-12"
    if period == "2013-now":
        return month >= "2013-01"
    if period == "realtime":
        return not revised
    return True


def by_state(history: dict[str, Any], prices: pd.Series) -> dict[str, Any]:
    months, states, revised = history["months"], history["state"], history["revised"]
    fwd = {h: [forward_return(prices, month_end(m), k) for m in months] for h, k in HORIZONS.items()}
    out: dict[str, Any] = {}
    for period, _ in PERIODS:
        keep = [_in_period(m, r, period) for m, r in zip(months, revised, strict=True)]
        rows = {}
        for h, k in HORIZONS.items():
            vals = [x for x, ok in zip(fwd[h], keep, strict=True) if ok]
            row = {"all": stats(vals, k)}
            for state, _ in STATES:
                row[state] = stats(
                    [x for x, s, ok in zip(fwd[h], states, keep, strict=True) if ok and s == state], k
                )
            long_, short = row["net_long"], row["net_short"]
            row["long_minus_short"] = (
                round(long_["mean"] - short["mean"], 2) if long_.get("n") and short.get("n") else None
            )
            rows[h] = row
        out[period] = rows
    return out


def by_signal(history: dict[str, Any], prices: pd.Series, horizon: str = "3m") -> list[dict[str, Any]]:
    months, k = history["months"], HORIZONS[horizon]
    fwd = [forward_return(prices, month_end(m), k) for m in months]
    out = []
    for sid, scores in history["signals"].items():
        row: dict[str, Any] = {"id": sid}
        for label, target in (("plus", 1), ("zero", 0), ("minus", -1)):
            row[label] = stats([x for x, s in zip(fwd, scores, strict=True) if s == target], k)
        p, m = row["plus"], row["minus"]
        row["spread"] = round(p["mean"] - m["mean"], 2) if p.get("n") and m.get("n") else None
        row["first_month"] = next((mo for mo, s in zip(months, scores, strict=True) if s is not None), None)
        out.append(row)
    return out


PRICE_ALERT_ROWS = [
    ("net_short", "data_weak_price_up", "Net short, S&P 500 in an uptrend (alert)"),
    ("net_short", None, "Net short, no alert"),
    ("net_long", "data_strong_price_down", "Net long, S&P 500 in a downtrend (alert)"),
    ("net_long", None, "Net long, no alert"),
]
PRICE_ALERT_ADDED = "2026-10"  # designed after reviewing 2022-24, so its history is in-sample


def by_price_alert(history: dict[str, Any], prices: pd.Series) -> dict[str, Any]:
    """How the S&P 500 did after months with and without the data-vs-prices alert (information only)."""
    flags = history.get("price_alert") or [None] * len(history["months"])
    fwd = {
        h: [forward_return(prices, month_end(m), k) for m in history["months"]] for h, k in HORIZONS.items()
    }
    rows = []
    for st, kind, label in PRICE_ALERT_ROWS:
        keep = [s == st and f == kind for s, f in zip(history["state"], flags, strict=True)]
        rows.append(
            {
                "state": st,
                "alert": kind,
                "label": label,
                **{
                    h: stats([x for x, ok in zip(fwd[h], keep, strict=True) if ok], k)
                    for h, k in HORIZONS.items()
                },
            }
        )
    return {
        "added": PRICE_ALERT_ADDED,
        "fired": sum(1 for f in flags if f),
        "rows": rows,
        "note": (
            "Added in October 2026 after reviewing the 2022-24 net short readings, so these numbers are in-sample: "
            "they show why the alert exists, not proof that it works. Its live record starts with the daily log."
        ),
    }


def exposure_curve(history: dict[str, Any], prices: pd.Series) -> dict[str, Any] | None:
    """Illustration only: hold the index with exposure +1 / 0 / -1 set by each month-end bias, no costs."""
    months, states = history["months"], history["state"]
    level_bh, level_bias = [100.0], [100.0]
    dates = []
    weight = {"net_long": 1, "neutral": 0, "net_short": -1}
    rets: list[tuple[float, float]] = []
    for m, s in zip(months, states, strict=True):
        r = forward_return(prices, month_end(m), 1)
        if r is None:
            continue
        w = weight.get(s, 0)
        if not dates:
            dates.append(month_end(m))
        level_bh.append(level_bh[-1] * (1 + r / 100))
        level_bias.append(level_bias[-1] * (1 + w * r / 100))
        dates.append(month_end(m) + pd.offsets.MonthEnd(1))
        rets.append((r, w * r))
    if len(rets) < 12:
        return None

    def summary(values: list[float], levels: list[float]) -> dict[str, float]:
        arr = np.array(values) / 100
        years = len(arr) / 12
        lv = np.array(levels)
        drawdown = (lv / np.maximum.accumulate(lv) - 1).min() * 100
        return {
            "cagr": round(((lv[-1] / lv[0]) ** (1 / years) - 1) * 100, 2),
            "vol": round(float(arr.std(ddof=1) * np.sqrt(12) * 100), 2),
            "max_drawdown": round(float(drawdown), 2),
        }

    idx = pd.DatetimeIndex(dates)
    return {
        "buy_and_hold": summary([a for a, _ in rets], level_bh),
        "bias_scaled": summary([b for _, b in rets], level_bias),
        "months": len(rets),
        "series": [
            line("Buy and hold", pd.Series(level_bh, index=idx), 2),
            line("Exposure set by the bias (+1 / 0 / -1)", pd.Series(level_bias, index=idx), 2),
        ],
    }


def _bands(history: dict[str, Any]) -> list[dict[str, str]]:
    """Shade the month that follows each net long / net short reading; consecutive months merge."""
    tone = {"net_long": "pos", "net_short": "neg"}
    out: list[dict[str, str]] = []
    for m, s in zip(history["months"], history["state"], strict=True):
        t = tone.get(s)
        if not t:
            continue
        a, b = month_end(m), month_end(m) + pd.offsets.MonthEnd(1)
        if out and out[-1]["tone"] == t and out[-1]["to"] == a.date().isoformat():
            out[-1]["to"] = b.date().isoformat()
        else:
            out.append({"from": a.date().isoformat(), "to": b.date().isoformat(), "tone": t})
    return out


def build_evidence(
    v: View, history: dict[str, Any], names: dict[str, str], log_start: str | None
) -> dict[str, Any]:
    assets = []
    sp = v.series("yahoo/GSPC")
    for aid, name, key in ASSETS:
        prices = v.series(key)
        if prices.empty:
            continue
        assets.append(
            {
                "id": aid,
                "name": name,
                "first": prices.index[0].date().isoformat(),
                "by_state": by_state(history, prices),
            }
        )
    curve = exposure_curve(history, sp)
    sp_m = sp.resample("ME").last().dropna()
    sp_m = sp_m[sp_m.index >= month_end(history["months"][0])] if history["months"] else sp_m
    bias = pd.Series(history["bias"], index=[month_end(m) for m in history["months"]], dtype=float).dropna()
    panels = [
        {
            **panel(
                "S&P 500 and the bias (shading = the month after a net long or net short reading)",
                "index",
                [line("S&P 500 (month-end)", sp_m, 1)],
            ),
            "bands": _bands(history),
        },
        panel(
            "Bias score at each month-end (point in time)",
            "score",
            [line("Bias", bias, 3)],
            refs=[(0.25, "Net long"), (-0.25, "Net short"), (0, "")],
        ),
    ]
    if curve:
        panels.append(
            {
                **panel(
                    "Illustration: S&P 500 held with the exposure the bias suggests (no costs, rebased to 100)",
                    "index",
                    curve.pop("series"),
                    refs=[(100, "Start")],
                    note="Not a trading system: the bias sets net exposure for a book of stock ideas, not an index position.",
                ),
                "rebase": True,
            }
        )
    months = history["months"]
    return {
        "as_of": v.as_of.isoformat(),
        "first_month": months[0] if months else None,
        "last_month": months[-1] if months else None,
        "months": len(months),
        "revised_months": int(sum(history["revised"])),
        "state_counts": {s: history["state"].count(s) for s, _ in STATES},
        "periods": [{"id": p, "label": label} for p, label in PERIODS],
        "horizons": list(HORIZONS),
        "states": [{"id": s, "label": label} for s, label in STATES],
        "assets": assets,
        "signals": [{**row, "name": names.get(row["id"], row["id"])} for row in by_signal(history, sp)],
        "exposure": curve,
        "price_alert": by_price_alert(history, sp),
        "panels": panels,
        "live_log_start": log_start,
    }
