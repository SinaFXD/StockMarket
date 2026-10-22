"""US regime, recession odds, Fed policy and the Treasury curve: ``site/data/regime.json``.

Context for the macro reading (lesson 3: growth and inflation; lessons 4-6: the yield curve and the Fed). Nothing
here feeds the bias. Parts:
- **regime**: growth (CFNAI 3-month average vs its trend of 0) against inflation momentum (core PCE over 6 months,
  annualised, minus the 12-month rate). Four regimes: recovery, overheat, stagflation, reflation;
- **history**: the regime each month-end could have been read with the data published by then (ALFRED vintages;
  months that needed revised data are flagged), and the forward returns of sector ETFs and asset-class ETFs after
  each regime month;
- **recession**: the New York Fed's probit on the 10y-3m spread, 12 months ahead, with NBER recessions;
- **taylor**: fed funds against a Taylor (1993) rule on core PCE and the output gap;
- **curve**: the Treasury curve from 1 month to 30 years, weekly for the last years (for the comparison slider).
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import REGIME
from ..signals.data import Library, View, month_ends
from ..signals.evidence import forward_return, month_end, stats
from ..store import iso, read_series, utc_now
from ..workbench.stock import SECTOR_ETF

CFNAI, CORE, SPREAD, USREC = "fred/CFNAI", "fred/PCEPILFE", "fred/T10Y3M", "fred/USREC"
FEDFUNDS, GDP, POTENTIAL = "fred/FEDFUNDS", "fred/GDPC1", "fred/GDPPOT"
CURVE = [
    ("1M", "DGS1MO", 1 / 12),
    ("3M", "DGS3MO", 0.25),
    ("6M", "DGS6MO", 0.5),
    ("1Y", "DGS1", 1),
    ("2Y", "DGS2", 2),
    ("3Y", "DGS3", 3),
    ("5Y", "DGS5", 5),
    ("7Y", "DGS7", 7),
    ("10Y", "DGS10", 10),
    ("20Y", "DGS20", 20),
    ("30Y", "DGS30", 30),
]
REGIMES = {
    "recovery": ("Recovery", "Growth at or above trend, inflation easing"),
    "overheat": ("Overheat", "Growth at or above trend, inflation rising"),
    "stagflation": ("Stagflation", "Growth below trend, inflation rising"),
    "reflation": ("Reflation", "Growth below trend, inflation easing"),
}
ASSETS = [
    ("SPY", "US stocks (S&P 500)"),
    ("IEF", "US Treasuries 7-10y"),
    ("GLD", "Gold"),
    ("DBC", "Commodities"),
    ("UUP", "US dollar"),
]
BENCHMARK = "SPY"


def _monthly(s: pd.Series) -> pd.Series:
    """One value per month, indexed by the month's first day."""
    if s.empty:
        return s
    out = s.copy()
    out.index = out.index.to_period("M").to_timestamp()
    return out[~out.index.duplicated(keep="last")].sort_index()


def growth(cfnai: pd.Series, p: dict) -> pd.Series:
    """CFNAI averaged over the last ``growth_months`` consecutive months."""
    m = _monthly(cfnai)
    if m.empty:
        return m
    m = m.asfreq("MS")
    return m.rolling(int(p["growth_months"]), min_periods=int(p["growth_months"])).mean().dropna()


def inflation_momentum(core: pd.Series, p: dict) -> pd.Series:
    """Core PCE inflation over ``inflation_short`` months (annualised) minus over ``inflation_long`` months, in pp."""
    m = _monthly(core)
    if m.empty:
        return m
    m = m.asfreq("MS")
    short, long = int(p["inflation_short"]), int(p["inflation_long"])
    fast = ((m / m.shift(short)) ** (12 / short) - 1) * 100
    slow = (m / m.shift(long) - 1) * 100
    return (fast - slow).dropna()


def yoy(s: pd.Series) -> pd.Series:
    m = _monthly(s).asfreq("MS")
    return ((m / m.shift(12) - 1) * 100).dropna()


def classify(g: float, i: float, p: dict) -> str:
    if g >= p["growth_trend"]:
        return "recovery" if i < 0 else "overheat"
    return "reflation" if i < 0 else "stagflation"


def reading(view: View, p: dict) -> dict[str, Any] | None:
    """The regime from the latest month both inputs cover."""
    g, i = growth(view.series(CFNAI), p), inflation_momentum(view.series(CORE), p)
    common = g.index.intersection(i.index)
    if common.empty:
        return None
    m = common[-1]
    core = view.series(CORE)
    core_yoy = yoy(core)
    regime = classify(float(g[m]), float(i[m]), p)
    fast = float(i[m]) + float(core_yoy.get(m, float("nan")))
    reason = (
        f"Chicago Fed activity index, 3-month average {g[m]:+.2f} "
        f"({'at or above' if g[m] >= p['growth_trend'] else 'below'} its trend of 0); core PCE inflation "
        f"{fast:.1f}% over the last {int(p['inflation_short'])} months annualised vs {core_yoy.get(m, float('nan')):.1f}% "
        f"over 12 months ({'rising' if i[m] >= 0 else 'easing'})."
    )
    return {
        "month": m.strftime("%Y-%m"),
        "growth": round(float(g[m]), 3),
        "inflation": round(float(i[m]), 3),
        "core_yoy": round(float(core_yoy[m]), 2) if m in core_yoy.index else None,
        "regime": regime,
        "label": REGIMES[regime][0],
        "borderline": bool(
            abs(g[m] - p["growth_trend"]) < p["borderline_growth"] or abs(i[m]) < p["borderline_inflation"]
        ),
        "reason_en": reason,
    }


def trail(view: View, p: dict) -> list[list[Any]]:
    g, i = growth(view.series(CFNAI), p), inflation_momentum(view.series(CORE), p)
    common = g.index.intersection(i.index)[-int(p["trail_months"]) :]
    return [
        [m.strftime("%Y-%m"), round(float(g[m]), 3), round(float(i[m]), 3), classify(g[m], i[m], p)]
        for m in common
    ]


def history(lib: Library, today: date, p: dict) -> list[dict[str, Any]]:
    """The regime as it could be read at each month-end, with the data published by then."""
    out = []
    for d in month_ends(p["history_start"], today):
        view = lib.view(d)
        r = reading(view, p)
        if r is None:
            continue
        out.append(
            {
                "month": d.strftime("%Y-%m"),
                "data_month": r["month"],
                "regime": r["regime"],
                "growth": r["growth"],
                "inflation": r["inflation"],
                "revised": bool(view.revised & {CFNAI, CORE}),
            }
        )
    return out


def _prices(site_data_dir: Path, sym: str) -> pd.Series:
    data = read_series(site_data_dir / "series" / "yahoo" / f"{sym}.json")
    if not data:
        return pd.Series(dtype=float)
    k = data.columns.index("adj_close") if "adj_close" in data.columns else 1
    pairs = [(r[0], r[k]) for r in data.rows if r[k] is not None]
    if not pairs:
        return pd.Series(dtype=float)
    return pd.Series([v for _, v in pairs], index=pd.to_datetime([d for d, _ in pairs])).sort_index()


def by_regime(
    hist: list[dict[str, Any]], prices: pd.Series, p: dict, benchmark: pd.Series | None = None
) -> dict[str, Any]:
    """Forward returns after each regime month (minus the benchmark's over the same months when given), per
    regime and for all months; for every month and for months read with real-time data only."""
    h = int(p["horizon_months"])
    rows = []
    for r in hist:
        start = month_end(r["month"])
        x = forward_return(prices, start, h)
        if x is not None and benchmark is not None:
            b = forward_return(benchmark, start, h)
            x = None if b is None else x - b
        if x is not None:
            rows.append((r["regime"], r["revised"], x))
    out: dict[str, Any] = {"first": None}
    first = next(
        (r["month"] for r in hist if forward_return(prices, month_end(r["month"]), h) is not None), None
    )
    out["first"] = first
    for period, keep in (("all", lambda rev: True), ("realtime", lambda rev: not rev)):
        sel = [(g, x) for g, rev, x in rows if keep(rev)]
        out[period] = {
            "any": stats([x for _, x in sel], h),
            **{g: stats([x for k, x in sel if k == g], h) for g in REGIMES},
        }
    return out


def normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def recession(view: View, today: date, p: dict) -> dict[str, Any] | None:
    """New York Fed model: P(recession in 12 months) = Φ(α + β × monthly average of the 10y-3m spread)."""
    s = view.series(SPREAD)
    if s.empty:
        return None
    monthly = s.groupby(s.index.to_period("M")).mean()
    monthly = monthly[monthly.index < pd.Period(today, "M")]  # complete months only
    monthly = monthly[monthly.index >= pd.Period(p["recession_start"], "M")]
    if monthly.empty:
        return None
    ahead = int(p["recession_ahead_months"])
    probs = [
        [
            (m + ahead).strftime("%Y-%m"),
            round(100 * normal_cdf(p["probit_alpha"] + p["probit_beta"] * v), 2),
            round(float(v), 3),
        ]
        for m, v in monthly.items()
    ]
    rec = _monthly(view.series(USREC))
    spans, start = [], None
    for m, v in rec.items():
        if v >= 1 and start is None:
            start = m
        if v < 1 and start is not None:
            spans.append([start.strftime("%Y-%m"), (m - pd.offsets.MonthBegin(1)).strftime("%Y-%m")])
            start = None
    if start is not None:
        spans.append([start.strftime("%Y-%m"), rec.index[-1].strftime("%Y-%m")])
    recessions = [s for s in spans if s[1] >= probs[0][0]]  # recessions the forecasts reach
    by_month = {m: pr for m, pr, _ in probs}
    for span in recessions:  # the highest probability the model gave, 12 months earlier, to a recession month
        inside = [pr for m, pr in by_month.items() if span[0] <= m <= span[1]]
        span.append(max(inside) if inside else None)
    last, prev = monthly.index[-1], monthly.index[-2] if len(monthly) > 1 else None
    return {
        "series": probs,
        "recessions": recessions,
        "usrec_last": rec.index[-1].strftime("%Y-%m") if not rec.empty else None,
        "latest": {
            "spread_month": last.strftime("%Y-%m"),
            "for_month": (last + ahead).strftime("%Y-%m"),
            "spread": round(float(monthly.iloc[-1]), 3),
            "prob": probs[-1][1],
            "prev": probs[-2][1] if prev is not None else None,
        },
    }


def taylor_rate(inflation: float, gap: float, p: dict) -> float:
    return (
        p["taylor_r_star"]
        + inflation
        + p["taylor_w_inflation"] * (inflation - p["taylor_target"])
        + p["taylor_w_gap"] * gap
    )


def taylor(view: View, p: dict) -> dict[str, Any] | None:
    """Fed funds against a Taylor (1993) rule: r* + π + 0.5 (π − 2) + 0.5 × output gap."""
    infl = yoy(view.series(CORE))
    gdp, pot = view.series(GDP), view.series(POTENTIAL)
    if infl.empty or gdp.empty or pot.empty:
        return None
    gap = (100 * (gdp / pot.reindex(gdp.index) - 1)).dropna()
    if gap.empty:
        return None
    gap_m = _monthly(gap).asfreq("MS").ffill()
    ff = _monthly(view.series(FEDFUNDS))
    months = infl.index[infl.index >= pd.Timestamp(f"{p['taylor_start']}-01")]
    rows = []
    for m in months:
        g = gap_m[gap_m.index <= m]
        if g.empty:
            continue
        rule = taylor_rate(float(infl[m]), float(g.iloc[-1]), p)
        rows.append(
            [
                m.strftime("%Y-%m"),
                round(float(ff[m]), 2) if m in ff.index else None,
                round(rule, 2),
                round(float(infl[m]), 2),
                round(float(g.iloc[-1]), 2),
            ]
        )
    if not rows:
        return None
    last = rows[-1]
    funds = view.series(FEDFUNDS)
    latest_ff = round(float(funds.iloc[-1]), 2) if not funds.empty else None
    return {
        "columns": ["month", "fed_funds", "taylor", "core_pce_yoy", "output_gap"],
        "rows": rows,
        "latest": {
            "month": last[0],
            "taylor": last[2],
            "inflation": last[3],
            "gap": last[4],
            "gap_quarter": gap.index[-1].strftime("%Y-%m"),
            "fed_funds": latest_ff,
            "fed_funds_month": funds.index[-1].strftime("%Y-%m") if not funds.empty else None,
            "gap_vs_rule": round(latest_ff - last[2], 2) if latest_ff is not None else None,
        },
    }


def curve(view: View, today: date, p: dict) -> dict[str, Any] | None:
    """Daily Treasury yields by maturity: the latest curve and one curve per week for the slider."""
    cols = {label: view.series(f"fred/{sid}") for label, sid, _ in CURVE}
    if cols["10Y"].empty:
        return None
    frame = pd.DataFrame(cols).dropna(subset=["10Y"])
    frame = frame[frame.index >= pd.Timestamp(today) - pd.DateOffset(years=int(p["curve_years"]))]
    if frame.empty:
        return None
    weekly = frame.groupby(frame.index.to_period("W-FRI")).tail(
        1
    )  # each week's last day (the latest included)

    def _row(r: pd.Series) -> list[float | None]:
        return [None if pd.isna(v) else round(float(v), 3) for v in r]

    return {
        "labels": [c[0] for c in CURVE],
        "years": [round(c[2], 4) for c in CURVE],
        "dates": [d.strftime("%Y-%m-%d") for d in weekly.index],
        "yields": [_row(r) for _, r in weekly.iterrows()],
    }


def build(
    site_data_dir: Path, today: date, lib: Library | None = None, p: dict | None = None
) -> dict[str, Any]:
    p = {**REGIME, **(p or {})}
    lib = lib or Library.load(today, site_data_dir=site_data_dir)
    view = lib.view(today)
    hist = history(lib, today, p)
    spy = _prices(site_data_dir, BENCHMARK)
    sectors = []
    for name, etf in SECTOR_ETF.items():
        px = _prices(site_data_dir, etf)
        if px.empty:
            continue
        sectors.append({"id": etf, "label": name, **by_regime(hist, px, p, benchmark=spy)})
    assets = []
    for sym, label in ASSETS:
        px = _prices(site_data_dir, sym)
        if px.empty:
            continue
        assets.append({"id": sym, "label": label, **by_regime(hist, px, p)})
    counts = {g: sum(1 for r in hist if r["regime"] == g) for g in REGIMES}
    return {
        "generated_at": iso(utc_now()),
        "params": p,
        "regimes": {k: {"label": v[0], "text": v[1]} for k, v in REGIMES.items()},
        "now": reading(view, p),
        "trail": trail(view, p),
        "history": [[r["month"], r["regime"], r["revised"]] for r in hist],
        "counts": counts,
        "realtime_from": next((r["month"] for r in hist if not r["revised"]), None),
        "sectors": sectors,
        "assets": assets,
        "recession": recession(view, today, p),
        "taylor": taylor(view, p),
        "curve": curve(view, today, p),
    }


def status_of(data: dict[str, Any]) -> dict[str, Any]:
    now = data.get("now") or {}
    rec = (data.get("recession") or {}).get("latest") or {}
    return {
        "status": "ok",
        "regime": now.get("label"),
        "month": now.get("month"),
        "recession_prob": rec.get("prob"),
        "history_months": len(data.get("history") or []),
    }
