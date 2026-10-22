"""The "11 numbers" per stock (lessons 22-25), the data-cleaning checks (lesson 28) and the sector averages.

11 numbers: price, market cap, EPS0 (last reported fiscal year), EPS1 and EPS2 (consensus for the current and
next fiscal year), EG1 = EPS1/EPS0 - 1, EG2 = EPS2/EPS1 - 1, PE1 = price/EPS1, PE2 = price/EPS2,
PEG1 = PE1 / (EG1 in %), PEG2 = PE2 / (EG2 in %).

Course rules that shape the arithmetic: a P/E only means something when EPS > 0; growth from a zero or
negative base is not a growth rate (it is a turnaround); a PEG with negative growth is meaningless.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from statistics import mean, median
from typing import Any

# check code -> (short label, explanation, excluded from sector averages?)
CHECKS: dict[str, tuple[str, str, bool]] = {
    "no_estimates": ("No estimates", "No consensus EPS for the current or next fiscal year.", True),
    "few_analysts": ("Few analysts", "Fewer analysts than the minimum behind the EPS estimates.", False),
    "stale": ("Stale estimates", "The estimates were downloaded too long ago.", False),
    "negative_eps": ("EPS ≤ 0", "A P/E (and PEG) is not meaningful when EPS is zero or negative.", False),
    "turnaround_base": (
        "Loss base",
        "EPS0 or EPS1 is zero or negative, so growth is not a rate (a turnaround, not growth).",
        False,
    ),
    "extreme_growth": ("Extreme growth", "EPS growth beyond the plausible range: check the source.", True),
    "extreme_pe": ("Extreme P/E", "P/E beyond the plausible range: usually depressed or one-off EPS.", True),
    "currency": (
        "Other currency",
        "The company reports, or analysts estimate, in another currency than the share price (most ADRs).",
        True,
    ),
    "feed_mismatch": (
        "Feeds disagree",
        "Yahoo's two estimate feeds disagree on EPS1: one of them is wrong (check before using).",
        True,
    ),
    "duplicate": ("Second share class", "Another share class of the same company is kept instead.", True),
    "foreign": ("Based abroad", "Headquarters outside the US (kept when it reports in US dollars).", False),
    "no_profile": ("Awaiting details", "Estimates and profile not downloaded yet.", True),
}
METRICS = ["mcap", "pe1", "pe2", "eg1", "eg2", "peg1", "peg2"]


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None  # NaN -> None


def _ratio_growth(new: float | None, old: float | None) -> float | None:
    """Growth in % from ``old`` to ``new``; only from a positive base."""
    if new is None or old is None or old <= 0:
        return None
    return (new / old - 1) * 100


def _pe(price: float | None, eps: float | None) -> float | None:
    return None if price is None or eps is None or eps <= 0 else price / eps


def _peg(pe: float | None, growth: float | None) -> float | None:
    return None if pe is None or growth is None or growth <= 0 else pe / growth


def _fy(end: Any) -> str | None:
    return str(end)[:7] if end else None


def compute(
    quote: dict[str, Any], summary: dict[str, Any] | None, fetched_at: str | None, today, p: dict
) -> dict:
    """One screener row. Estimates come from the per-stock summary; price and market cap from the screener."""
    flags: list[str] = []
    s = summary or {}
    y0, y1 = s.get("0y") or {}, s.get("+1y") or {}
    price, mcap = _num(quote.get("regularMarketPrice")), _num(quote.get("marketCap"))
    eps0, eps1, eps2 = _num(y0.get("eps_year_ago")), _num(y0.get("eps")), _num(y1.get("eps"))
    if summary is None:
        flags.append("no_profile")
        eps1, eps2 = (
            _num(quote.get("epsCurrentYear")),
            _num(quote.get("epsForward")),
        )  # screener values meanwhile
    if eps1 is None or eps2 is None:
        flags.append("no_estimates")
    analysts = _num(y0.get("analysts"))
    if summary is not None and (analysts is None or analysts < p["min_analysts"]):
        flags.append("few_analysts")
    if fetched_at:
        age = (today - datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).date()).days
        if age > p["stale_estimates_days"]:
            flags.append("stale")
    eg1, eg2 = _ratio_growth(eps1, eps0), _ratio_growth(eps2, eps1)
    pe1, pe2 = _pe(price, eps1), _pe(price, eps2)
    if any(e is not None and e <= 0 for e in (eps1, eps2)):
        flags.append("negative_eps")
    if any(e is not None and e <= 0 for e in (eps0, eps1)):
        flags.append("turnaround_base")
    if any(g is not None and abs(g) > p["extreme_growth_pct"] for g in (eg1, eg2)):
        flags.append("extreme_growth")
    if any(x is not None and x > p["extreme_pe"] for x in (pe1, pe2)):
        flags.append("extreme_pe")
    price_ccy = quote.get("currency") or s.get("currency")
    others = {y0.get("eps_currency"), quote.get("financialCurrency")} - {None}
    if price_ccy and any(c != price_ccy for c in others):
        flags.append("currency")
    screener_eps1 = _num(quote.get("epsCurrentYear"))
    if summary is not None and eps1 and screener_eps1 and eps1 > 0 and screener_eps1 > 0:
        if abs(screener_eps1 / eps1 - 1) * 100 > p["feed_mismatch_pct"]:
            flags.append("feed_mismatch")
    country = s.get("country")
    if country and country != "United States":
        flags.append("foreign")
    rev1, rev0, rev2 = _num(y0.get("rev")), _num(y0.get("rev_year_ago")), _num(y1.get("rev"))
    eps1_90 = _num(y0.get("eps_90d_ago"))
    return {
        "t": quote.get("symbol"),
        "name": quote.get("longName") or quote.get("shortName"),
        "sector": quote.get("sector"),
        "industry": s.get("industry"),
        "country": country,
        "price": price,
        "mcap": mcap,
        "eps0": eps0,
        "eps1": eps1,
        "eps2": eps2,
        "eg1": eg1,
        "eg2": eg2,
        "pe1": pe1,
        "pe2": pe2,
        "peg1": _peg(pe1, eg1),
        "peg2": _peg(pe2, eg2),
        "fy": _fy(y0.get("end")),
        "analysts": analysts,
        "rev1": rev1,
        "rev2": rev2,
        "rg1": _ratio_growth(rev1, rev0),
        "rg2": _ratio_growth(rev2, rev1),
        "eps1_rev90": _ratio_growth(eps1, eps1_90) if eps1_90 and eps1_90 > 0 else None,
        "earnings": _earnings_date(s.get("earnings_date") or quote.get("earningsTimestamp")),
        "volume": _num(quote.get("averageDailyVolume3Month")),
        "flags": flags,
    }


def _earnings_date(ts: Any) -> str | None:
    v = _num(ts)
    return datetime.fromtimestamp(v, tz=UTC).date().isoformat() if v else None


def _base_name(name: str | None) -> str:
    n = (name or "").lower()
    n = re.sub(r"\b(class|series|cl)\s+[a-z]\b", "", n)
    return re.sub(r"[^a-z0-9]", "", n)


def _same_company(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Two lines with the same name are one company when their reported EPS or their P/E match (share classes
    such as BRK-A/BRK-B differ in price and EPS per share, not in P/E); a line without estimates is a
    preferred or tracking line of the same issuer."""
    if a["eps1"] is None or b["eps1"] is None:
        return True
    if a["eps0"] and b["eps0"] and abs(a["eps0"] / b["eps0"] - 1) < 0.01:
        return True
    return bool(a["pe1"] and b["pe1"] and abs(a["pe1"] / b["pe1"] - 1) < 0.05)


def mark_duplicates(rows: list[dict[str, Any]]) -> None:
    """Share classes of one company (GOOG/GOOGL, BRK-A/BRK-B): keep one line, the one with usable numbers
    first, then the most traded."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        key = _base_name(r["name"])
        if key:
            groups.setdefault(key, []).append(r)
    for members in groups.values():
        if len(members) < 2:
            continue
        ranked = sorted(members, key=lambda r: (included(r), r["volume"] or 0, r["mcap"] or 0), reverse=True)
        keep = ranked[0]
        for r in ranked[1:]:
            if _same_company(keep, r):
                r["flags"].append("duplicate")
                r["duplicate_of"] = keep["t"]


def included(row: dict[str, Any]) -> bool:
    """Counts toward sector averages: no flag that makes its numbers unreliable."""
    return not any(CHECKS[f][2] for f in row["flags"])


def group_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Average and median of each metric over the included stocks (values that are not meaningful are skipped)."""
    use = [r for r in rows if included(r)]
    out: dict[str, Any] = {"n": len(rows), "n_used": len(use)}
    for m in METRICS:
        vals = [r[m] for r in use if r[m] is not None]
        out[m] = {
            "n": len(vals),
            "mean": round(mean(vals), 3) if vals else None,
            "median": round(median(vals), 3) if vals else None,
        }
    return out


def sector_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sectors = sorted({r["sector"] for r in rows if r["sector"]})
    return {
        "all": group_stats(rows),
        **{s: group_stats([r for r in rows if r["sector"] == s]) for s in sectors},
    }
