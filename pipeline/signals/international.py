"""International (lessons 4, 13-14): euro-area ESI, China's private vs official PMIs, and the money markets of
Japan, the UK, Germany and Italy read with the US template (curve and real rate)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .base import Signal, fmt, iso, months_back, ordinal, pct_rank, window
from .data import View
from .money_markets import curve_reading, real_rate_reading

BLOCK = "international"


def esi(v: View, p: dict) -> Signal:
    sig = Signal(
        "esi",
        "Euro-area Economic Sentiment (ESI)",
        BLOCK,
        ">= 100 and rising over 3 months -> +1; < 100 and falling -> -1; else 0. Zones at +-1.5 SD (115 / 85).",
        ["eurostat/ESI_EA"],
    )
    s = v.series("eurostat/ESI_EA")
    if why := v.stale("eurostat/ESI_EA", s):
        return sig.awaiting(why)
    cur, then = float(s.iloc[-1]), months_back(s, 3)
    ch = None if then is None else cur - then
    mid, zone = p["esi_neutral"], p["esi_sd"] * p["esi_zone_sd"]
    sig.as_of, sig.percentile_10y = iso(s.index[-1])[:7], pct_rank(window(s, p["percentile_years"]), cur)
    sig.metrics = {"esi": cur, "change_3m": ch}
    above, used = 0, 0
    for cc in ESI_COUNTRIES:
        c = v.series(f"eurostat/ESI_{cc}")
        if c.empty or v.stale(f"eurostat/ESI_{cc}", c):
            continue
        used += 1
        above += int(c.iloc[-1] >= mid)
        sig.metrics[f"esi_{cc.lower()}"] = float(c.iloc[-1])
    if used:
        sig.metrics["countries_above_100"] = f"{above} of {used}"
    if cur >= mid + zone:
        sig.flags.append(f"Peak zone (>= {mid + zone:.0f}).")
    elif cur <= mid - zone:
        sig.flags.append(f"Trough zone (<= {mid - zone:.0f}): sharp falls have tended to mark troughs.")
    base = f"ESI {cur:.1f} (long-term average 100, {fmt(ch, 1, True)} over 3 months)"
    if cur >= mid and ch is not None and ch > 0:
        return sig.set(1, "Above average & rising", f"{base}: euro-area sentiment is improving.")
    if cur < mid and ch is not None and ch < 0:
        return sig.set(-1, "Below average & falling", f"{base}: euro-area sentiment is deteriorating.")
    return sig.set(0, "Mixed", f"{base}.")


def china(v: View, p: dict) -> Signal:
    sig = Signal(
        "china",
        "China PMI (RatingDog, private)",
        BLOCK,
        "RatingDog manufacturing >= 50 and rising over 3 months -> +1; < 50 and falling -> -1; else 0. The official "
        "NBS PMI is shown but not scored; 'potential lie' when official > 50 and private < 50.",
        ["manual/china_pmi"],
    )
    rd = v.manual("china_pmi", "ratingdog_manufacturing")
    if why := v.manual_stale("china_pmi", "ratingdog_manufacturing", rd):
        return sig.awaiting(why)
    nbs = v.manual("china_pmi", "nbs_manufacturing")
    cur, then = float(rd.iloc[-1]), months_back(rd, 3)
    ch = None if then is None else cur - then
    lvl = p["china_neutral"]
    sig.as_of, sig.percentile_10y = iso(rd.index[-1])[:7], pct_rank(window(rd, p["percentile_years"]), cur)
    sig.metrics = {"ratingdog_manufacturing": cur, "change_3m": ch}
    official = None
    if not nbs.empty and nbs.index[-1] == rd.index[-1]:
        official = float(nbs.iloc[-1])
        gap = (rd - nbs).dropna()
        lies = int(((nbs.reindex(gap.index) > lvl) & (rd.reindex(gap.index) < lvl)).sum())
        sig.metrics.update(
            {
                "nbs_manufacturing": official,
                "private_minus_official": cur - official,
                "potential_lie_months": lies,
                "months_compared": len(gap),
            }
        )
        if official > lvl and cur < lvl:
            sig.flags.append(
                f"Potential lie: official NBS {official:.1f} > 50 while private RatingDog {cur:.1f} < 50."
            )
    base = f"RatingDog {cur:.1f} ({fmt(ch, 1, True)} over 3 months)" + (
        f", official NBS {official:.1f} (gap {cur - official:+.1f})" if official is not None else ""
    )
    if cur >= lvl and ch is not None and ch > 0:
        return sig.set(1, "Expanding & rising", f"{base}: private-sector manufacturing is improving.")
    if cur < lvl and ch is not None and ch < 0:
        return sig.set(-1, "Contracting & falling", f"{base}: private-sector manufacturing is weakening.")
    return sig.set(0, "Mixed", f"{base}.")


# --------------------------------------------------------------------------------------------------------
# Other countries' money markets (lesson 4: "the same template applies to Japan, UK, Germany, Italy";
# lesson 14: China's real rate). Monthly OECD data: 10y yield, short rate, CPI YoY.

ESI_COUNTRIES = ["DE", "FR", "IT", "ES", "NL"]
COUNTRIES = {"JP": "Japan", "GB": "UK", "DE": "Germany", "IT": "Italy", "CN": "China"}
SCORED = ["JP", "GB", "DE", "IT"]  # China: shown, not scored (its bonds are mostly domestic, lesson 14)
SHORT_LABEL = {"CN": "3m interbank"}


@dataclass
class CountryRates:
    code: str
    name: str
    status: str = "awaiting"
    why: str = ""
    score: int | None = None
    curve: dict[str, Any] = field(default_factory=dict)
    real: dict[str, Any] = field(default_factory=dict)
    y10: float | None = None
    short: float | None = None
    cpi: float | None = None
    as_of: str | None = None
    cpi_month: str | None = None

    def summary(self) -> str:
        if self.status != "ok":
            return f"{self.name} awaiting data"
        c, r = self.curve, self.real
        return (
            f"{self.name} {_sc(self.score)} (curve {c['value']:+.2f}pp {c['state'].lower()} {_sc(c['score'])}; "
            f"real rate {r['value']:+.2f}%, {ordinal(r['percentile'])} pct, {r['state'].lower()} {_sc(r['score'])})"
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "status": self.status,
            "why": self.why,
            "score": self.score,
            "scored": self.code in SCORED,
            "yield_10y": self.y10,
            "short_rate": self.short,
            "short_label": SHORT_LABEL.get(self.code, "overnight"),
            "cpi_yoy": self.cpi,
            "cpi_month": self.cpi_month,
            "as_of": self.as_of,
            "curve": self.curve,
            "real": self.real,
        }


def _sc(x: int) -> str:
    return f"{x:+d}" if x else "0"


def _sub(v: View, kind: str, cc: str) -> tuple[str, pd.Series]:
    key = f"oecd/{kind}_{cc}"
    return key, v.series(key)


def country_rates(v: View, p: dict, cc: str) -> CountryRates:
    """One country's curve (10y - short rate) and real 10y (10y - CPI YoY), read with the US rules."""
    out = CountryRates(cc, COUNTRIES[cc])
    parts = [_sub(v, k, cc) for k in ("Y10", "RATE", "CPI")]
    for key, s in parts:
        if why := v.stale(key, s):
            out.why = f"{key.split('/')[1]}: {why}"
            return out
    (_, y10), (_, short), (_, cpi) = parts
    curve_m = (y10 - short).dropna()
    real_m = (y10 - cpi).dropna()
    if len(curve_m) < 4 or len(real_m) < 24:
        out.why = "not enough history"
        return out
    # curve: latest month both rates exist; 3-month change in monthly observations
    c_now, c_then = float(curve_m.iloc[-1]), months_back(curve_m, 3)
    c_ch = None if c_then is None else c_now - c_then
    c_score, c_state, c_why, c_dir = curve_reading(c_now, c_ch, p)
    # real rate: latest yield minus latest published CPI, as for the US
    r_now = float(y10.iloc[-1]) - float(cpi.iloc[-1])
    y_then, i_then = months_back(y10, 3), months_back(cpi, 3)
    r_then = None if y_then is None or i_then is None else y_then - i_then
    rising = r_then is not None and r_now > r_then
    pct = pct_rank(window(real_m, p["percentile_years"]), r_now)
    r_score, r_state = real_rate_reading(pct, rising, p)
    total = c_score + r_score
    out.status, out.score = "ok", (total > 0) - (total < 0)
    out.y10, out.short, out.cpi = float(y10.iloc[-1]), float(short.iloc[-1]), float(cpi.iloc[-1])
    out.as_of, out.cpi_month = iso(curve_m.index[-1])[:7], iso(cpi.index[-1])[:7]
    out.curve = {
        "value": c_now,
        "change_3m": c_ch,
        "direction": c_dir,
        "state": c_state,
        "score": c_score,
        "reason": c_why,
        "percentile": pct_rank(window(curve_m, p["percentile_years"]), c_now),
    }
    out.real = {
        "value": r_now,
        "then": r_then,
        "rising": rising,
        "percentile": pct,
        "state": r_state,
        "score": r_score,
    }
    return out


def intl_money_markets(v: View, p: dict) -> Signal:
    sig = Signal(
        "intl_money_markets",
        "International money markets (Japan, UK, Germany, Italy)",
        BLOCK,
        "Each country read with the US template: curve (10y - short rate) and real 10y (10y - CPI YoY); country = "
        "the sign of the two. Net of the countries >= +2 -> +1, <= -2 -> -1, else 0. China shown, not scored.",
        [f"oecd/{k}_{cc}" for cc in SCORED for k in ("Y10", "RATE", "CPI")],
    )
    rows = [country_rates(v, p, cc) for cc in SCORED]
    ok = [r for r in rows if r.status == "ok"]
    if len(ok) < p["intl_min_countries"]:
        missing = "; ".join(f"{r.name}: {r.why}" for r in rows if r.status != "ok")
        return sig.awaiting(f"fewer than {p['intl_min_countries']} countries with data ({missing})")
    net = sum(r.score for r in ok)
    sig.as_of = max(r.as_of for r in ok)
    sig.metrics = {f"{r.name.lower()}_score": r.score for r in ok}
    sig.metrics["net"] = net
    for r in ok:
        if r.curve["value"] < 0:
            sig.flags.append(f"{r.name} curve inverted: 10y - short rate is {r.curve['value']:+.2f}pp.")
    italy, germany = (
        next((r for r in ok if r.code == "IT"), None),
        next((r for r in ok if r.code == "DE"), None),
    )
    if italy and germany:
        sig.metrics["italy_germany_10y_spread"] = italy.y10 - germany.y10
    detail = "; ".join(r.summary() for r in rows)
    need = p["intl_net"]
    if net >= need:
        return sig.set(1, "Supportive", f"{detail}. Net {net:+d}: liquidity abroad supports risk assets.")
    if net <= -need:
        return sig.set(
            -1, "Tightening", f"{detail}. Net {net:+d}: money markets abroad are signalling stress."
        )
    return sig.set(0, "Mixed", f"{detail}. Net {net:+d}: no clear message from abroad.")


SIGNALS = [esi, china, intl_money_markets]
