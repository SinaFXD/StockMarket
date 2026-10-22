"""The Global page (``site/data/macro/global.json``): money markets country by country and regional equity
dispersion (US vs Europe vs Japan vs China).

Lesson 15 asks where the cycle is in each region and whether a move is global or local. Equity dispersion is
context for that question, not a score: nothing here enters the bias except the international money-markets
signal, which uses the same country readings (``international.country_rates``).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .base import fmt, iso, monthly, pct_change, pct_rank, value_at, window, yoy_monthly
from .charts import grid, line, panel
from .data import View
from .international import COUNTRIES, SCORED, country_rates
from .money_markets import curve_direction

# region -> (name, local index key, local label, USD ETF key, ETF label)
REGIONS = [
    ("US", "United States", "yahoo/GSPC", "S&P 500", "yahoo/SPY", "SPY"),
    ("EU", "Europe", "yahoo/STOXX", "STOXX Europe 600", "yahoo/VGK", "VGK"),
    ("JP", "Japan", "yahoo/N225", "Nikkei 225", "yahoo/EWJ", "EWJ"),
    ("CN", "China", "yahoo/000001_SS", "Shanghai Composite", "yahoo/MCHI", "MCHI"),
]
PERIODS = {"1m": 30, "3m": 91, "6m": 182, "12m": 365}
LABELS = {"1m": "1 month", "3m": "3 months", "6m": "6 months", "12m": "12 months"}


def _us_rates(v: View, p: dict) -> dict[str, Any]:
    """The US row of the money-markets table, on the same definitions as the other countries."""
    y, short, cpi = v.series("fred/DGS10"), v.series("fred/DGS3MO"), v.series("fred/CPIAUCSL")
    row: dict[str, Any] = {"code": "US", "name": "United States", "scored": False, "short_label": "3m bill"}
    if y.empty or short.empty or cpi.empty:
        return {**row, "status": "awaiting", "why": "no data yet"}
    infl = yoy_monthly(cpi)
    real_m = (monthly(y) - infl).dropna()
    c_now = float(y.iloc[-1]) - float(short.iloc[-1])
    c_then = value_at((y - short).dropna(), y.index[-1] - pd.Timedelta(days=p["lookback_days"]))
    r_now = float(y.iloc[-1]) - float(infl.iloc[-1])
    return {
        **row,
        "status": "ok",
        "yield_10y": float(y.iloc[-1]),
        "short_rate": float(short.iloc[-1]),
        "cpi_yoy": float(infl.iloc[-1]),
        "cpi_month": iso(infl.index[-1])[:7],
        "as_of": iso(y.index[-1]),
        "curve": {
            "value": c_now,
            "change_3m": None if c_then is None else c_now - c_then,
            "direction": curve_direction(None if c_then is None else c_now - c_then, p),
        },
        "real": {"value": r_now, "percentile": pct_rank(window(real_m, p["percentile_years"]), r_now)},
    }


def _stats(s: pd.Series) -> dict[str, Any] | None:
    if len(s) < 30:
        return None
    last = float(s.iloc[-1])
    prev_year_end = value_at(s, pd.Timestamp(year=s.index[-1].year, month=1, day=1) - pd.Timedelta(days=1))
    ma200 = float(s.iloc[-200:].mean()) if len(s) >= 200 else None
    high = float(window(s, 1).max())
    return {
        "last": last,
        "date": iso(s.index[-1]),
        **{f"r{k}": pct_change(s, d) for k, d in PERIODS.items()},
        "ytd": None if not prev_year_end else (last / prev_year_end - 1) * 100,
        "vs_ma200": None if ma200 is None else (last / ma200 - 1) * 100,
        "from_high": (last / high - 1) * 100,
    }


def _round(x: Any) -> Any:
    if isinstance(x, float):
        return round(x, 3)
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v) for v in x]
    return x


def dispersion(regions: list[dict[str, Any]], period: str = "3m") -> dict[str, Any]:
    """Is the move global or local? Uses the USD ETFs so every region is in the same currency."""
    rets = [
        (r["name"], r["usd"][f"r{period}"])
        for r in regions
        if r.get("usd") and r["usd"][f"r{period}"] is not None
    ]
    if len(rets) < 3:
        return {"reading": "Not enough regions with data.", "period": period}
    rets.sort(key=lambda x: x[1], reverse=True)
    up = [n for n, x in rets if x > 0]
    down = [n for n, x in rets if x <= 0]
    spread = rets[0][1] - rets[-1][1]
    if not down:
        reading = "Every region is up: a global move, consistent with a synchronised expansion."
    elif not up:
        reading = "Every region is down: a global move, consistent with a synchronised slowdown or risk-off."
    else:
        reading = (
            f"Dispersion: {', '.join(up)} up, {', '.join(down)} down. Regional growth, liquidity and currency "
            "differences are driving returns; read each region's own indicators."
        )
    return {
        "period": period,
        "leader": rets[0][0],
        "leader_return": rets[0][1],
        "laggard": rets[-1][0],
        "laggard_return": rets[-1][1],
        "spread": spread,
        "up": len(up),
        "total": len(rets),
        "reading": f"Over {LABELS[period]} in US dollars: {rets[0][0]} leads ({fmt(rets[0][1], 1, True)}%), "
        f"{rets[-1][0]} lags ({fmt(rets[-1][1], 1, True)}%), a {spread:.1f}pp spread. {reading}",
    }


def _ratio(a: pd.Series, b: pd.Series) -> pd.Series:
    df = pd.concat([a, b], axis=1).ffill().dropna()
    return (df.iloc[:, 0] / df.iloc[:, 1]).dropna()


def build_global(v: View, p: dict) -> dict[str, Any]:
    countries = [_us_rates(v, p)] + [country_rates(v, p, cc).to_json() for cc in COUNTRIES]
    regions = []
    for code, name, local, local_label, usd, usd_label in REGIONS:
        regions.append(
            {
                "code": code,
                "name": name,
                "local_label": local_label,
                "usd_label": usd_label,
                "local": _stats(v.series(local)),
                "usd": _stats(v.series(usd)),
            }
        )
    us = regions[0]["usd"]
    for r in regions[1:]:
        if r["usd"] and us:
            r["vs_us"] = {
                k: None
                if r["usd"][f"r{k}"] is None or us[f"r{k}"] is None
                else r["usd"][f"r{k}"] - us[f"r{k}"]
                for k in ("3m", "12m")
            }

    real_charts, curve_charts = [], []
    us_y, us_cpi = v.series("fred/DGS10"), v.series("fred/CPIAUCSL")
    if not us_y.empty and not us_cpi.empty:
        real_charts.append(
            panel(
                "United States",
                "%",
                [line("Real 10y", (monthly(us_y) - yoy_monthly(us_cpi)).dropna())],
                refs=[(0, "0")],
            )
        )
        curve_charts.append(
            panel(
                "United States", "pp", [line("10y - 3m", monthly(v.series("fred/T10Y3M")))], refs=[(0, "0")]
            )
        )
    for cc, name in COUNTRIES.items():
        y, short, cpi = (v.series(f"oecd/{k}_{cc}") for k in ("Y10", "RATE", "CPI"))
        tag = "" if cc in SCORED else " (not scored)"
        real_charts.append(panel(name + tag, "%", [line("Real 10y", (y - cpi).dropna())], refs=[(0, "0")]))
        curve_charts.append(
            panel(name + tag, "pp", [line("10y - short", (y - short).dropna())], refs=[(0, "0")])
        )
    panels = [
        grid("Real 10y rates (10y yield - CPI YoY)", "%", real_charts),
        grid("Yield curves (10y yield - short rate)", "pp", curve_charts),
        {
            **panel(
                "Regional equities, local currency (rebased to 100)",
                "index",
                [line(r[3], v.series(r[2]), 2) for r in REGIONS],
                refs=[(100, "Start")],
            ),
            "rebase": True,
        },
        {
            **panel(
                "Regional equities in US dollars: ETFs (rebased to 100)",
                "index",
                [line(f"{r[5]} ({r[1]})", v.series(r[4]), 2) for r in REGIONS],
                refs=[(100, "Start")],
            ),
            "rebase": True,
        },
        {
            **panel(
                "Relative strength vs the US (ETF / SPY, rebased to 100)",
                "ratio",
                [
                    line(f"{r[1]} vs US", _ratio(v.series(r[4]), v.series("yahoo/SPY")), 4)
                    for r in REGIONS[1:]
                ],
                refs=[(100, "Same as US")],
                note="Rising line = the region is beating the US in dollar terms.",
            ),
            "rebase": True,
        },
    ]
    return _round(
        {
            "as_of": v.as_of.isoformat(),
            "countries": countries,
            "regions": regions,
            "dispersion": dispersion(regions),
            "dispersion_12m": dispersion(regions, "12m"),
            "panels": panels,
        }
    )
