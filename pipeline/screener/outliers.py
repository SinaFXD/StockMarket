"""Outlier classification (lessons 25-27): where each stock sits against its own sector.

The course reads a stock against its sector averages: positive outliers (long candidates) have the highest EPS
growth, ideally positive in both forward years; negative outliers (short candidates) the lowest, ideally negative
in both; in between sit post-growth stocks (fast growth now, much slower next year), turnarounds (out of
losses or out of a decline), value traps (cheap for a reason: falling earnings) and "boring" stocks.

The course gives no cut-offs, so positions use percentiles of the sector's clean stocks (``config.SCREENER``:
top/bottom quarter, *tune*). Rules are tried in the order of ``CATEGORIES``; every stock gets one category and a
plain-English reason. This is a first reading: the trade-idea work decides.
"""

from __future__ import annotations

from bisect import bisect_right
from statistics import median
from typing import Any

from .numbers import included

# code -> (label, side, description)
CATEGORIES: dict[str, tuple[str, str, str]] = {
    "positive": ("Positive outlier", "long", "EPS growth in the sector's top quarter in both forward years."),
    "negative": (
        "Negative outlier",
        "short",
        "EPS falling in both forward years and in the sector's bottom quarter, or profits turning into losses.",
    ),
    "post_growth": (
        "Post-growth",
        "short",
        "Top-quarter growth this year, bottom-quarter growth next year: the growth phase is ending.",
    ),
    "turnaround": (
        "Turnaround",
        "either",
        "Back to profit after a loss, or EPS falling this year and recovering above the sector median next year.",
    ),
    "value_trap": (
        "Value trap",
        "either",
        "Cheap P/E (sector's bottom quarter) while EPS is falling: cheap for a reason.",
    ),
    "boring": ("Boring", "none", "Growth in the middle half of the sector in both years."),
    "mixed": ("In between", "none", "None of the patterns above."),
    "loss": ("Loss-making", "none", "Losses in both forward years: growth and P/E are not meaningful."),
    "na": ("Not classified", "none", "A data check keeps this stock out of the comparison."),
}


def _pct(sorted_vals: list[float], x: float | None) -> float | None:
    """Share of the peers at or below ``x`` (0-100)."""
    if x is None or not sorted_vals:
        return None
    return round(bisect_right(sorted_vals, x) / len(sorted_vals) * 100, 1)


def _peers(rows: list[dict[str, Any]], min_peers: int) -> dict[str, list[dict[str, Any]]]:
    clean = [r for r in rows if included(r)]
    out = {}
    for sector in {r["sector"] for r in rows}:
        mine = [r for r in clean if r["sector"] == sector]
        out[sector] = mine if len(mine) >= min_peers else clean
    return out


def _fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:+.0f}%"


def _rule(r: dict[str, Any], top: float, bottom: float) -> tuple[str, str]:
    eg1, eg2, p1, p2, pe_pct = r["eg1"], r["eg2"], r["eg1_pct"], r["eg2_pct"], r["pe1_pct"]
    eps0, eps1, eps2 = r["eps0"], r["eps1"], r["eps2"]
    growth = f"EPS growth {_fmt(eg1)} this year, {_fmt(eg2)} next year"
    if not included(r):
        return "na", "A data check keeps it out of the sector comparison."
    if eps1 is not None and eps2 is not None and eps1 > 0 and eps2 <= 0:
        return "negative", f"Profits expected to turn into losses next year (EPS {eps1:.2f} to {eps2:.2f})."
    if eg1 is not None and eg2 is not None and p1 is not None and p2 is not None:
        if eg1 > 0 and eg2 > 0 and p1 >= top and p2 >= top:
            return "positive", f"{growth}: both in the top quarter of the sector (consecutive growth)."
        if eg1 < 0 and eg2 < 0 and p1 <= bottom and p2 <= bottom:
            return "negative", f"{growth}: both falling and in the bottom quarter of the sector."
        if eg1 > 0 and p1 >= top and p2 <= bottom:
            return "post_growth", f"{growth}: fast growth now, among the slowest in the sector next year."
    if eps0 is not None and eps1 is not None and eps0 <= 0 < eps1:
        return "turnaround", f"Back to profit: EPS {eps0:.2f} last year, {eps1:.2f} expected this year."
    if eps1 is not None and eps2 is not None and eps1 <= 0 and eps2 <= 0:
        return "loss", "Losses expected in both forward years."
    if eg1 is not None and eg2 is not None and eg1 < 0 < eg2 and p2 is not None and p2 >= 50:
        return "turnaround", f"{growth}: a fall this year, recovery above the sector median next year."
    if (
        pe_pct is not None
        and pe_pct <= bottom
        and ((eg1 is not None and eg1 < 0) or (eg2 is not None and eg2 < 0))
    ):
        return "value_trap", f"P/E in the cheapest quarter of the sector while EPS falls ({growth[11:]})."
    if p1 is not None and p2 is not None and bottom < p1 < top and bottom < p2 < top:
        return "boring", f"{growth}: middle of the pack in both years."
    return "mixed", f"{growth}."


def classify(rows: list[dict[str, Any]], p: dict) -> dict[str, dict[str, Any]]:
    """Adds ``eg1_pct``, ``eg2_pct``, ``pe1_pct``, ``pe_prem``, ``cls``, ``why`` and ``notes`` to every row;
    returns the medians used per sector."""
    peers = _peers(rows, int(p["min_peers"]))
    medians: dict[str, dict[str, Any]] = {}
    dists: dict[str, dict[str, list[float]]] = {}
    for sector, group in peers.items():
        dists[sector] = {m: sorted(r[m] for r in group if r[m] is not None) for m in ("eg1", "eg2", "pe1")}
        medians[sector] = {m: (round(median(v), 3) if v else None) for m, v in dists[sector].items()} | {
            "peers": len(group)
        }
    for r in rows:
        d, med = dists[r["sector"]], medians[r["sector"]]
        r["eg1_pct"], r["eg2_pct"] = _pct(d["eg1"], r["eg1"]), _pct(d["eg2"], r["eg2"])
        r["pe1_pct"] = _pct(d["pe1"], r["pe1"])
        r["pe_prem"] = (r["pe1"] / med["pe1"] - 1) * 100 if r["pe1"] and med["pe1"] else None
        r["cls"], r["why"] = _rule(r, p["top_pct"], p["bottom_pct"])
        r["notes"] = notes(r)
    return medians


def notes(r: dict[str, Any]) -> list[str]:
    """The supporting evidence the course looks for next to the growth pattern."""
    out = []
    rg1, rg2 = r.get("rg1"), r.get("rg2")
    if rg1 is not None and rg2 is not None:
        if rg1 > 0 and rg2 > 0:
            out.append("sales growing both years")
        elif rg1 < 0 and rg2 < 0:
            out.append("sales falling both years")
    rev = r.get("eps1_rev90")
    if rev is not None and abs(rev) >= 2:
        out.append(f"EPS1 estimate {'raised' if rev > 0 else 'cut'} {abs(rev):.0f}% in 90 days")
    prem = r.get("pe_prem")
    if prem is not None and abs(prem) >= 20:
        out.append(f"P/E {abs(prem):.0f}% {'above' if prem > 0 else 'below'} the sector median")
    return out
