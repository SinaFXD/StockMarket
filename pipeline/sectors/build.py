"""Sectors side by side (lessons 22-29: the screener works sector by sector; sectors are cyclical or defensive):
``site/data/sectors.json``.

Per sector, from the published files:
- **fundamentals** of its clean stocks (no "left out" check): medians of EPS growth, P/E, PEG, sales growth, the
  share of stocks whose EPS consensus was raised / cut in 90 days, and how many stocks of each type;
- **price**: its SPDR ETF against SPY over 1, 3 and 6 months, the relative line, and a rotation reading
  (relative strength and its recent change: leading, weakening, lagging, improving);
- **macro**: the stock-weighted net effect of the macro drivers on its industries (``themes.json``);
- the largest long and short candidates.
Groups (Morningstar's super-sectors, which use Yahoo's sector names): cyclical, sensitive, defensive; and the
cyclical + sensitive basket against the defensive one. Context only: nothing here changes the bias or the types.
"""

from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any

from ..config import SECTORS
from ..screener.numbers import included
from ..store import iso, read_json, read_series, utc_now
from ..workbench.stock import SECTOR_ETF

GROUPS = {
    "cyclical": ["Basic Materials", "Consumer Cyclical", "Financial Services", "Real Estate"],
    "sensitive": ["Communication Services", "Energy", "Industrials", "Technology"],
    "defensive": ["Consumer Defensive", "Healthcare", "Utilities"],
}
GROUP_OF = {s: g for g, members in GROUPS.items() for s in members}
LONG = ("positive",)
SHORT = ("negative", "post_growth")


def _rows(table: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not table:
        return []
    cols = table["columns"]
    return [dict(zip(cols, r, strict=False)) for r in table["rows"]]


def _series(site_data_dir: Path, sym: str) -> tuple[list[str], list[float]]:
    data = read_series(site_data_dir / "series" / "yahoo" / f"{sym}.json")
    if not data:
        return [], []
    k = data.columns.index("adj_close") if "adj_close" in data.columns else 1
    pairs = [(r[0], r[k]) for r in data.rows if r[k] is not None]
    return [d for d, _ in pairs], [v for _, v in pairs]


def _med(values: list[float | None]) -> float | None:
    v = [x for x in values if x is not None]
    return round(median(v), 3) if v else None


def fundamentals(rows: list[dict[str, Any]], p: dict) -> dict[str, Any]:
    clean = [r for r in rows if _clean(r)]
    rev = [r["eps1_rev90"] for r in clean if r.get("eps1_rev90") is not None]
    counts = {}
    for r in rows:
        counts[r["cls"]] = counts.get(r["cls"], 0) + 1
    return {
        "n": len(rows),
        "n_clean": len(clean),
        "mcap": sum(r["mcap"] or 0 for r in rows),
        "eg1": _med([r["eg1"] for r in clean]),
        "eg2": _med([r["eg2"] for r in clean]),
        "pe1": _med([r["pe1"] for r in clean]),
        "peg1": _med([r["peg1"] for r in clean]),
        "rg1": _med([r.get("rg1") for r in clean]),
        "rv": _med([r.get("rv") for r in clean]),
        "r3m": _med([r.get("r3m") for r in clean]),
        "rev_up": round(100 * sum(1 for x in rev if x >= p["revision_pct"]) / len(rev), 1) if rev else None,
        "rev_down": round(100 * sum(1 for x in rev if x <= -p["revision_pct"]) / len(rev), 1)
        if rev
        else None,
        "types": counts,
    }


def _clean(r: dict[str, Any]) -> bool:
    return included({"flags": r.get("flags") or []})


def candidates(rows: list[dict[str, Any]], types: tuple[str, ...], n: int) -> list[dict[str, Any]]:
    """The largest stocks of the given types, those passing the volatility filter first."""
    pick = [r for r in rows if r["cls"] in types]
    pick.sort(key=lambda r: (r.get("vol_ok") is not True, -(r["mcap"] or 0)))
    keys = ("t", "name", "industry", "cls", "mcap", "eg1", "eg2", "pe1", "vol_ok")
    return [{k: r.get(k) for k in keys} for r in pick[:n]]


def ret(values: list[float], days: int) -> float | None:
    if len(values) <= days or not values[-days - 1]:
        return None
    return (values[-1] / values[-days - 1] - 1) * 100


def relative(dates: list[str], values: list[float], spy: dict[str, float]) -> tuple[list[str], list[float]]:
    """ETF ÷ SPY on their common days."""
    pairs = [(d, v / spy[d]) for d, v in zip(dates, values, strict=False) if spy.get(d)]
    return [d for d, _ in pairs], [v for _, v in pairs]


def rotation(rel: list[float], p: dict) -> dict[str, Any] | None:
    """Relative strength over ~3 months (x) and its change over the last month (y), in percentage points.
    Leading: outperforming and gaining; weakening: outperforming but losing it; lagging: underperforming and
    still losing; improving: underperforming but catching up."""
    lb, mom = int(p["rs_days"]), int(p["rs_momentum_days"])
    if len(rel) <= lb + mom:
        return None
    rs_now = (rel[-1] / rel[-lb - 1] - 1) * 100
    rs_then = (rel[-mom - 1] / rel[-lb - mom - 1] - 1) * 100
    change = rs_now - rs_then
    quadrant = (
        ("leading" if change >= 0 else "weakening")
        if rs_now >= 0
        else ("improving" if change >= 0 else "lagging")
    )
    return {"rs": round(rs_now, 2), "change": round(change, 2), "quadrant": quadrant}


def macro_wind(rows: list[dict[str, Any]], themes: dict[str, Any] | None) -> dict[str, Any] | None:
    """Stock-weighted average of the industries' net macro effect, and the industries with the strongest winds."""
    if not themes:
        return None
    net = {s["industry"]: s["net"] for s in themes.get("industries", []) if s["net"] is not None}
    counts: dict[str, int] = {}
    for r in rows:
        if r.get("industry") in net:
            counts[r["industry"]] = counts.get(r["industry"], 0) + 1
    if not counts:
        return None
    total = sum(counts.values())
    score = sum(net[i] * n for i, n in counts.items()) / total
    ranked = sorted(counts, key=lambda i: -net[i])
    return {
        "score": round(score, 2),
        "tailwinds": [[i, net[i]] for i in ranked if net[i] > 0][:3],
        "headwinds": [[i, net[i]] for i in reversed(ranked) if net[i] < 0][:3],
    }


def build(site_data_dir: Path, p: dict | None = None) -> dict[str, Any]:
    p = {**SECTORS, **(p or {})}
    stocks = read_json(site_data_dir / "screener" / "stocks.json")
    themes = read_json(site_data_dir / "themes.json")
    latest = read_json(site_data_dir / "macro" / "latest.json") or {}
    rows = _rows(stocks)
    spy_dates, spy_values = _series(site_data_dir, "SPY")
    spy = dict(zip(spy_dates, spy_values, strict=False))
    spark = int(p["spark_days"])
    sectors = []
    rel_lines: dict[str, tuple[list[str], list[float]]] = {}
    for name, etf in SECTOR_ETF.items():
        mine = [r for r in rows if r["sector"] == name]
        dates, values = _series(site_data_dir, etf)
        rd, rv = relative(dates, values, spy)
        rel_lines[name] = (rd, rv)
        base = rv[-spark - 1] if len(rv) > spark else (rv[0] if rv else None)
        sectors.append(
            {
                "sector": name,
                "etf": etf,
                "group": GROUP_OF[name],
                "fundamentals": fundamentals(mine, p),
                "price": {
                    "last": values[-1] if values else None,
                    "date": dates[-1] if dates else None,
                    **{f"r{m}m": ret(values, d) for m, d in ((1, 21), (3, 63), (6, 126))},
                    **{
                        f"rs{m}m": _diff(ret(values, d), ret(spy_values, d))
                        for m, d in ((1, 21), (3, 63), (6, 126))
                    },
                },
                "rotation": rotation(rv, p),
                "relative_line": [
                    [d, round(v / base * 100, 2)] for d, v in zip(rd[-spark:], rv[-spark:], strict=False)
                ]
                if base
                else [],
                "macro": macro_wind(mine, themes),
                "long": candidates(mine, LONG, int(p["candidates"])),
                "short": candidates(mine, SHORT, int(p["candidates"])),
            }
        )
    groups = group_view(rel_lines, spy_dates, p)
    bias = latest.get("bias") or {}
    return {
        "generated_at": iso(utc_now()),
        "as_of": (stocks or {}).get("as_of"),
        "prices_as_of": spy_dates[-1] if spy_dates else None,
        "params": p,
        "bias": {"state": bias.get("state"), "label": bias.get("label"), "score": bias.get("score")},
        "groups": groups,
        "agreement": agreement(bias.get("state"), groups.get("spread_3m"), p),
        "sectors": sectors,
    }


def _diff(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else round(a - b, 2)


def group_view(rel_lines: dict, spy_dates: list[str], p: dict) -> dict[str, Any]:
    """Equal-weight baskets of each group's relative lines; the cyclical + sensitive basket ÷ the defensive one
    over the last year (start = 100)."""
    days = spy_dates[-int(p["group_days"]) - 1 :]
    if not days:
        return {}

    def basket(names: list[str]) -> list[float | None]:
        out = []
        maps = [dict(zip(*rel_lines[n], strict=False)) for n in names if rel_lines[n][0]]
        bases = [m.get(days[0]) for m in maps]
        for d in days:
            vals = [m[d] / b for m, b in zip(maps, bases, strict=False) if b and m.get(d)]
            out.append(sum(vals) / len(vals) if vals else None)
        return out

    risk_on = basket(GROUPS["cyclical"] + GROUPS["sensitive"])
    defensive = basket(GROUPS["defensive"])
    ratio = [(a / b * 100) if a and b else None for a, b in zip(risk_on, defensive, strict=False)]
    pairs = [(d, round(v, 2)) for d, v in zip(days, ratio, strict=False) if v is not None]

    def change(n: int) -> float | None:
        vals = [v for _, v in pairs]
        return round((vals[-1] / vals[-n - 1] - 1) * 100, 2) if len(vals) > n else None

    out = {"ratio": [[d, v] for d, v in pairs], "spread_1m": change(21), "spread_3m": change(63)}
    for g, names in GROUPS.items():
        b = basket(names)
        vals = [v for v in b if v is not None]
        out[f"{g}_3m"] = round((vals[-1] / vals[-64] - 1) * 100, 2) if len(vals) > 63 else None
    return out


def agreement(bias_state: str | None, spread_3m: float | None, p: dict) -> dict[str, Any] | None:
    """Does the market's own preference (cyclicals vs defensives over 3 months) agree with the macro bias?"""
    if spread_3m is None:
        return None
    thr = p["rotation_pp"]
    market = "cyclical" if spread_3m >= thr else "defensive" if spread_3m <= -thr else "mixed"
    if bias_state is None:
        verdict = "no bias"
    elif market == "mixed" or bias_state == "neutral":
        verdict = "mixed"
    else:
        verdict = "agree" if (market == "cyclical") == (bias_state == "net_long") else "disagree"
    return {"market": market, "verdict": verdict}
