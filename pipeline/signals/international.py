"""International (lessons 13-14): euro-area ESI and China's private vs official PMIs."""

from __future__ import annotations

from .base import Signal, fmt, iso, months_back, pct_rank, window
from .data import View

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


SIGNALS = [esi, china]
