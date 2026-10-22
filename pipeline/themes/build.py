"""Macro-driven ideas and international listings (lessons 34-35): ``site/data/themes.json``.

1. Industry map: each Yahoo industry collects the effects of the Macro Desk signals and of the ISM industry lists
   that reach it (``map.yaml``); net > 0 = macro tailwind, < 0 = headwind.
2. Macro-driven ideas: the screener's long-side types in tailwind industries and short-side types in headwind
   industries.
3. International: stocks headquartered outside the US (mostly ADRs) by region, ranked on growth (EPS growth is
   currency-neutral; P/E is not when the EPS is in another currency), and the China check: official PMI vs what
   analysts expect from Chinese companies.

Built from the published files (``stocks.json``, ``macro/latest.json``, ``manual/*.json``), so it runs after the
screener and the Macro Desk. Context only: nothing here feeds the bias.
"""

from __future__ import annotations

import re
from pathlib import Path
from statistics import median
from typing import Any

import yaml

from ..config import THEMES
from ..store import read_json

MAP_FILE = Path(__file__).with_name("map.yaml")
LONG_TYPES = {"positive": "long", "turnaround": "either"}
SHORT_TYPES = {"negative": "short", "post_growth": "short", "value_trap": "either"}


def load_map(path: Path = MAP_FILE) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def norm(name: str) -> str:
    """ISM names are typed by hand: compare without case, punctuation or 'and' vs '&'."""
    s = name.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def last_month(table: dict[str, Any] | None) -> str | None:
    """Month of the last row of a published manual file (None when the file is missing or empty)."""
    rows = (table or {}).get("rows") or []
    return rows[-1][0] if rows else None


def rows_of(table: dict[str, Any]) -> list[dict[str, Any]]:
    cols = table["columns"]
    return [dict(zip(cols, r, strict=False)) for r in table["rows"]]


# -- 1. industry map ---------------------------------------------------------------------------------------
def signal_effects(mapping: dict[str, Any], signals: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per (theme, industry): effect = sign x signal score; None when the signal awaits data."""
    out = []
    for theme in mapping["signals"]:
        sig = signals.get(theme["signal"]) or {}
        score = sig.get("score") if sig.get("status", "ok") == "ok" else None
        for industry, sign in theme["industries"].items():
            out.append(
                {
                    "industry": industry,
                    "source": "macro",
                    "theme": theme["id"],
                    "label": theme["label"],
                    "effect": None if score is None else sign * score,
                    "reading": sig.get("state") or "awaiting data",
                    "as_of": sig.get("as_of"),
                    "why": theme["why"] + ("" if sign > 0 else " (works the other way here)"),
                    "etf": theme.get("etf"),
                }
            )
    return out


def ism_effects(
    mapping: dict[str, Any], ism_rows: list[dict[str, Any]], expected: dict[str, str | None]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Growth / contraction lists of the latest ISM reports. ``expected``: the month of the latest headline report
    per report type; an industry list for an older month is "awaiting data" (never used stale)."""
    out: list[dict[str, Any]] = []
    status: dict[str, Any] = {}
    for report, names in mapping["ism"].items():
        lookup = {norm(k): (k, v) for k, v in names.items()}
        rows = [r for r in ism_rows if r["report"] == report]
        month = max((r["month"] for r in rows), default=None)
        want = expected.get(report)
        fresh = month is not None and (want is None or month >= want)
        unknown = []
        listed = {}
        if fresh:
            for r in rows:
                if r["month"] != month:
                    continue
                hit = lookup.get(norm(r["industry"]))
                if not hit:
                    unknown.append(r["industry"])
                    continue
                listed[hit[0]] = r
        # consecutive months each ISM industry has kept its status (growth or contraction)
        streaks = {}
        for ism_name in listed:
            st = listed[ism_name]["status"]
            n = 0
            for m in sorted({r["month"] for r in rows}, reverse=True):
                same = [
                    r
                    for r in rows
                    if r["month"] == m and lookup.get(norm(r["industry"]), (None,))[0] == ism_name
                ]
                if same and same[0]["status"] == st:
                    n += 1
                else:
                    break
            streaks[ism_name] = n
        status[report] = {
            "month": month,
            "expected": want,
            "status": "ok" if fresh else "awaiting",
            "unknown": unknown,
            "growth": sorted(k for k, r in listed.items() if r["status"] == "growth"),
            "contraction": sorted(k for k, r in listed.items() if r["status"] == "contraction"),
        }
        for ism_name, industries in names.items():
            r = listed.get(ism_name)
            effect = None if not fresh else (1 if r and r["status"] == "growth" else -1 if r else 0)
            for industry in industries:
                out.append(
                    {
                        "industry": industry,
                        "source": "ism",
                        "theme": f"ism_{report}",
                        "label": f"ISM {report}: {ism_name}",
                        "effect": effect,
                        "reading": (
                            "awaiting data"
                            if not fresh
                            else f"{r['status']} ({streaks[ism_name]} month{'s' if streaks[ism_name] > 1 else ''})"
                            if r
                            else "not listed (no change)"
                        ),
                        "as_of": month,
                        "why": (r or {}).get("comment") or "",
                        "etf": None,
                    }
                )
    return out, status


def industry_scores(effects: list[dict[str, Any]], counts: dict[str, int], p: dict) -> list[dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for e in effects:
        by.setdefault(e["industry"], []).append(e)
    out = []
    for industry, items in by.items():
        used = [e["effect"] for e in items if e["effect"] is not None]
        net = sum(used) if used else None
        if net is None:
            tone = None
        elif abs(net) >= p["strong"]:
            tone = "strong tailwind" if net > 0 else "strong headwind"
        elif abs(net) >= p["tailwind"]:
            tone = "tailwind" if net > 0 else "headwind"
        else:
            tone = "neutral"
        out.append(
            {
                "industry": industry,
                "net": net,
                "tone": tone,
                "stocks": counts.get(industry, 0),
                "items": items,
            }
        )
    out.sort(key=lambda x: (-(x["net"] if x["net"] is not None else -99), x["industry"]))
    return out


# -- 2. macro-driven ideas -----------------------------------------------------------------------------------
def macro_ideas(rows: list[dict[str, Any]], scores: list[dict[str, Any]], bias: str | None) -> dict[str, Any]:
    tone = {s["industry"]: s for s in scores}
    longs, shorts = [], []
    for r in rows:
        s = tone.get(r.get("industry") or "")
        if not s or s["net"] is None:
            continue
        pick = {
            "t": r["t"],
            "name": r["name"],
            "sector": r["sector"],
            "industry": r["industry"],
            "cls": r["cls"],
            "net": s["net"],
            "mcap": r["mcap"],
            "eg1": r["eg1"],
            "eg2": r["eg2"],
            "pe1": r["pe1"],
            "r3m": r.get("r3m"),
            "vol_ok": r.get("vol_ok"),
            "why": r.get("why"),
        }
        if (s["tone"] or "").endswith("tailwind") and r["cls"] in LONG_TYPES:
            longs.append(pick)
        elif (s["tone"] or "").endswith("headwind") and r["cls"] in SHORT_TYPES:
            shorts.append(pick)

    def key(x: dict[str, Any]) -> tuple:
        return (-abs(x["net"]), x["cls"] not in ("positive", "negative", "post_growth"), -(x["mcap"] or 0))

    return {"bias": bias, "long": sorted(longs, key=key), "short": sorted(shorts, key=key)}


# -- 3. international ------------------------------------------------------------------------------------------
def region_of(country: str | None, mapping: dict[str, Any]) -> str | None:
    if not country or country == "United States":
        return None
    for region, countries in mapping["regions"].items():
        if country in countries:
            return region
    return "Other"


def _pct_rank(values: list[float], x: float) -> float:
    return 100 * sum(1 for v in values if v <= x) / len(values)


def international(rows: list[dict[str, Any]], mapping: dict[str, Any], p: dict) -> dict[str, Any]:
    """Foreign-headquartered listings, a growth rank among them and medians per region."""
    intl = []
    for r in rows:
        region = region_of(r.get("country"), mapping)
        if not region or "duplicate" in r["flags"] or "no_estimates" in r["flags"]:
            continue
        other_ccy = "currency" in r["flags"]
        cap = p["max_growth_pct"]

        def growth(v: float | None, cap: float = cap) -> float | None:
            """Growth beyond the cap is a data or currency problem: left out."""
            return v if v is not None and abs(v) <= cap else None

        intl.append(
            {
                "t": r["t"],
                "name": r["name"],
                "country": r["country"],
                "region": region,
                "sector": r["sector"],
                "industry": r["industry"],
                "mcap": r["mcap"],
                "eg1": growth(r["eg1"]),
                "eg2": growth(r["eg2"]),
                # Yahoo mixes currencies in these listings' sales estimates: sales growth left out
                "rg1": None if other_ccy else growth(r.get("rg1")),
                "rg2": None if other_ccy else growth(r.get("rg2")),
                "eps1_rev90": r.get("eps1_rev90"),
                "pe1": None if other_ccy else r["pe1"],  # EPS in another currency: P/E not comparable
                "other_currency": other_ccy,
                "r3m": r.get("r3m"),
                "rv": r.get("rv"),
                "cls": r["cls"],
            }
        )
    eg1s = [x["eg1"] for x in intl if x["eg1"] is not None]
    eg2s = [x["eg2"] for x in intl if x["eg2"] is not None]
    for x in intl:
        x["eg1_pct"] = _pct_rank(eg1s, x["eg1"]) if x["eg1"] is not None and eg1s else None
        x["eg2_pct"] = _pct_rank(eg2s, x["eg2"]) if x["eg2"] is not None and eg2s else None
        top, bottom = p["top_pct"], p["bottom_pct"]
        if (
            x["eg1"] is not None
            and x["eg2"] is not None
            and x["eg1"] > 0
            and x["eg2"] > 0
            and min(x["eg1_pct"], x["eg2_pct"]) >= top
        ):
            x["rank"] = "leader"
        elif (
            x["eg1"] is not None
            and x["eg2"] is not None
            and x["eg1"] < 0
            and x["eg2"] < 0
            and max(x["eg1_pct"], x["eg2_pct"]) <= bottom
        ):
            x["rank"] = "laggard"
        else:
            x["rank"] = None
    regions = {}
    for region in sorted({x["region"] for x in intl}):
        group = [x for x in intl if x["region"] == region]
        regions[region] = {
            "n": len(group),
            **{k: _median(group, k) for k in ("eg1", "eg2", "rg1", "eps1_rev90", "r3m")},
        }
    intl.sort(key=lambda x: -(x["mcap"] or 0))
    return {"stocks": intl, "regions": regions}


def _median(group: list[dict[str, Any]], key: str) -> float | None:
    vals = [x[key] for x in group if x.get(key) is not None]
    return round(median(vals), 3) if vals else None


def china_check(signal: dict[str, Any] | None, regions: dict[str, Any], p: dict) -> dict[str, Any]:
    """Lesson 14: official Chinese data is unreliable; Chinese companies listed in the US report under US rules.
    Compare the official PMI's message (expansion or not) with the direction of analysts' estimate revisions
    for Chinese listings."""
    m = (signal or {}).get("metrics") or {}
    nbs, private = m.get("nbs_manufacturing"), m.get("ratingdog_manufacturing")
    china = regions.get("China") or {}
    rev, n = china.get("eps1_rev90"), china.get("n", 0)
    out = {
        "nbs": nbs,
        "ratingdog": private,
        "gap": m.get("private_minus_official"),
        "potential_lie_months": m.get("potential_lie_months"),
        "companies_n": n,
        "companies_rev90": rev,
        "companies_rg1": china.get("rg1"),
        "as_of": (signal or {}).get("as_of"),
    }
    if nbs is None or rev is None or n < p["china_min_stocks"]:
        out.update(
            state="awaiting",
            text="Not enough data: the China PMIs (manual file) or Chinese listings are missing.",
        )
        return out
    official_up = nbs >= 50
    companies_up = rev > 0
    if official_up and not companies_up:
        out.update(
            state="disagree",
            text=(
                f"The official PMI says expansion ({nbs:.1f}) but analysts have cut Chinese companies' earnings "
                f"(median {rev:+.1f}% in 90 days, {n} stocks): trust the companies, not the official number."
            ),
        )
    elif not official_up and companies_up:
        out.update(
            state="disagree",
            text=(
                f"The official PMI says contraction ({nbs:.1f}) while analysts are raising Chinese companies' "
                f"earnings (median {rev:+.1f}% in 90 days, {n} stocks): the companies look better than the data."
            ),
        )
    else:
        out.update(
            state="agree",
            text=(
                f"Official PMI {nbs:.1f} and analysts' revisions for Chinese companies (median {rev:+.1f}% in 90 days, "
                f"{n} stocks) point the same way."
            ),
        )
    return out


# -- assemble ----------------------------------------------------------------------------------------------
def build(
    site_data_dir: Path, mapping: dict[str, Any] | None = None, p: dict | None = None
) -> dict[str, Any]:
    mapping = mapping or load_map()
    p = {**THEMES, **(p or {})}
    stocks = read_json(site_data_dir / "screener" / "stocks.json")
    latest = read_json(site_data_dir / "macro" / "latest.json") or {}
    manual = {
        n: read_json(site_data_dir / "manual" / f"{n}.json")
        for n in ("ism_industries", "ism_manufacturing", "ism_services")
    }
    rows = rows_of(stocks) if stocks else []
    signals = {s["id"]: s for s in latest.get("signals", [])}
    ism_rows = rows_of(manual["ism_industries"]) if manual["ism_industries"] else []
    expected = {k: last_month(manual[f"ism_{k}"]) for k in ("manufacturing", "services")}
    effects = signal_effects(mapping, signals)
    ism, ism_status = ism_effects(mapping, ism_rows, expected)
    counts: dict[str, int] = {}
    for r in rows:
        if r.get("industry"):
            counts[r["industry"]] = counts.get(r["industry"], 0) + 1
    scores = industry_scores(effects + ism, counts, p)
    known = set(counts)
    bias = (latest.get("bias") or {}).get("state")
    intl = international(rows, mapping, p)
    return {
        "as_of": (stocks or {}).get("as_of"),
        "macro_as_of": latest.get("as_of"),
        "params": p,
        "bias": latest.get("bias"),
        "ism": ism_status,
        "industries": scores,
        "unmapped_industries": sorted(known - {s["industry"] for s in scores}),
        "unknown_industries": sorted({s["industry"] for s in scores} - known) if known else [],
        "ideas": macro_ideas(rows, scores, bias),
        "international": intl,
        "china": china_check(signals.get("china"), intl["regions"], p),
    }


def status_of(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok" if data["industries"] else "failed",
        "industries": sum(1 for s in data["industries"] if s["net"] is not None),
        "tailwinds": sum(1 for s in data["industries"] if (s["tone"] or "").endswith("tailwind")),
        "headwinds": sum(1 for s in data["industries"] if (s["tone"] or "").endswith("headwind")),
        "long_ideas": len(data["ideas"]["long"]),
        "short_ideas": len(data["ideas"]["short"]),
        "international": len(data["international"]["stocks"]),
        "ism": {k: v["status"] for k, v in data["ism"].items()},
    }
