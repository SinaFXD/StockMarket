"""US surveys (lessons 7-11): ISM Manufacturing & Services, UMich, building permits, NFIB."""

from __future__ import annotations

import pandas as pd

from .base import Signal, fmt, iso, months_back, pct_rank, streak, window, yoy_monthly
from .data import View

BLOCK = "surveys"

ISM_M_PARTS = [
    ("new_orders", "New Orders"),
    ("production", "Production"),
    ("employment", "Employment"),
    ("supplier_deliveries", "Supplier Deliveries"),
    ("inventories", "Inventories"),
]


def _trend_text(v: View, file: str, parts: list[tuple[str, str]], level: float) -> tuple[dict, list[str]]:
    lengths, notes = {}, []
    for col, label in parts:
        s = v.manual(file, col)
        if s.empty:
            continue
        n, side, capped = streak(s, level)
        lengths[col] = {"months": n, "side": side, "at_least": capped}
        notes.append(f"{label} {s.iloc[-1]:.1f} ({side} 50 for {'>=' if capped else ''}{n} mo)")
    return lengths, notes


def ism_manufacturing(v: View, p: dict) -> Signal:
    sig = Signal(
        "ism_manufacturing",
        "ISM Manufacturing PMI",
        BLOCK,
        "PMI >= 50 and New Orders >= 50 -> +1; both < 50 -> -1; else 0. New Orders lead the headline.",
        ["manual/ism_manufacturing"],
    )
    pmi, no = v.manual("ism_manufacturing", "pmi"), v.manual("ism_manufacturing", "new_orders")
    if why := v.manual_stale("ism_manufacturing", "pmi", pmi):
        return sig.awaiting(why)
    if no.empty or no.index[-1] != pmi.index[-1]:
        return sig.awaiting("New Orders missing for the latest month")
    month = pmi.index[-1]
    cur, orders = float(pmi.iloc[-1]), float(no.iloc[-1])
    inv = v.manual("ism_manufacturing", "inventories")
    lvl = p["ism_neutral"]
    lengths, notes = _trend_text(v, "ism_manufacturing", ISM_M_PARTS, lvl)
    n, side, capped = streak(pmi, lvl)
    sig.as_of, sig.percentile_10y = iso(month)[:7], pct_rank(window(pmi, p["percentile_years"]), cur)
    sig.metrics = {
        "pmi": cur,
        "new_orders": orders,
        "pmi_streak": {"months": n, "side": side, "at_least": capped},
        "components": lengths,
    }
    if not inv.empty and inv.index[-1] == month:
        spread = orders - float(inv.iloc[-1])
        sig.metrics["orders_minus_inventories"] = spread
        if spread > 0:
            sig.flags.append(f"New Orders exceed Inventories by {spread:.1f}: orders are leading.")
    if cur >= p["ism_peak"]:
        sig.flags.append(f"Near a cyclical peak (PMI >= {p['ism_peak']:.0f}; peaks have been ~60).")
    if cur <= p["ism_trough"]:
        sig.flags.append(f"Near a cyclical trough (PMI <= {p['ism_trough']:.0f}; troughs have been 40-45).")
    base = (
        f"PMI {cur:.1f} ({side} 50 for {'>=' if capped else ''}{n} mo), New Orders {orders:.1f}. "
        + "; ".join(notes[1:])
        + "."
    )
    if cur >= lvl and orders >= lvl:
        return sig.set(1, "Expanding", f"{base} Expansion with growing orders.")
    if cur < lvl and orders < lvl:
        return sig.set(-1, "Contracting", f"{base} Contraction with falling orders.")
    lead = (
        "orders turning up ahead of the headline" if orders >= lvl else "orders falling ahead of the headline"
    )
    return sig.set(0, "Mixed", f"{base} Mixed: {lead}.")


ISM_S_PARTS = [
    ("business_activity", "Business Activity"),
    ("new_orders", "New Orders"),
    ("employment", "Employment"),
    ("supplier_deliveries", "Supplier Deliveries"),
]


def ism_services(v: View, p: dict) -> Signal:
    sig = Signal(
        "ism_services",
        "ISM Services PMI",
        BLOCK,
        "Composite, Business Activity and New Orders all >= 50 -> +1; composite < 50 or both BA and NO < 50 -> -1; "
        "else 0. Backlog of Orders as confirmation.",
        ["manual/ism_services"],
    )
    pmi = v.manual("ism_services", "pmi")
    if why := v.manual_stale("ism_services", "pmi", pmi):
        return sig.awaiting(why)
    month = pmi.index[-1]
    ba, no, bl = (v.manual("ism_services", c) for c in ("business_activity", "new_orders", "backlog"))
    if ba.empty or no.empty or ba.index[-1] != month or no.index[-1] != month:
        return sig.awaiting("Business Activity or New Orders missing for the latest month")
    cur, act, orders = float(pmi.iloc[-1]), float(ba.iloc[-1]), float(no.iloc[-1])
    lvl = p["ism_neutral"]
    lengths, notes = _trend_text(v, "ism_services", ISM_S_PARTS, lvl)
    sig.as_of, sig.percentile_10y = iso(month)[:7], pct_rank(window(pmi, p["percentile_years"]), cur)
    sig.metrics = {"pmi": cur, "business_activity": act, "new_orders": orders, "components": lengths}
    if not bl.empty and bl.index[-1] == month:
        sig.metrics["backlog"] = float(bl.iloc[-1])
        confirm = "confirms" if (bl.iloc[-1] >= lvl) == (cur >= lvl) else "does not confirm"
        sig.flags.append(f"Backlog of Orders {bl.iloc[-1]:.1f} {confirm} the headline.")
    base = f"Services PMI {cur:.1f}. " + "; ".join(notes) + "."
    if cur >= lvl and act >= lvl and orders >= lvl:
        return sig.set(1, "Expanding", f"{base} Services (~80% of the economy) are expanding.")
    if cur < lvl or (act < lvl and orders < lvl):
        return sig.set(-1, "Contracting", f"{base} Services are contracting.")
    return sig.set(0, "Mixed", f"{base} Mixed: activity and orders disagree.")


def umich(v: View, p: dict) -> Signal:
    sig = Signal(
        "umich",
        "UMich consumer sentiment",
        BLOCK,
        "Expectations down >= 10 points in 3 months -> -1; several (3) readings < 70 -> -1; above 80 and not "
        "falling -> +1; else 0. Zones: 95-110 peak, 70-95 balanced, 55-70 trough.",
        ["umich/ICS", "umich/ICE", "umich/ICC"],
    )
    ics, ice, icc = v.series("umich/ICS"), v.series("umich/ICE"), v.series("umich/ICC")
    if why := v.stale("umich/ICS", ics) or v.stale("umich/ICE", ice):
        return sig.awaiting(why)
    ics, ice = ics[ics.index >= "1978-01-01"], ice[ice.index >= "1978-01-01"]  # monthly since 1978
    cur, exp = float(ics.iloc[-1]), float(ice.iloc[-1])
    exp_then, cur_then = months_back(ice, 3), months_back(ics, 3)
    exp_ch = None if exp_then is None else exp - exp_then
    cur_ch = None if cur_then is None else cur - cur_then
    zone = (
        "Peak zone"
        if cur >= p["umich_peak"]
        else "Balanced"
        if cur >= p["umich_pessimistic"]
        else "Trough zone"
        if cur >= p["umich_trough"]
        else "Below trough zone"
    )
    sig.as_of, sig.percentile_10y = iso(ics.index[-1])[:7], pct_rank(window(ics, p["percentile_years"]), cur)
    sig.metrics = {
        "sentiment": cur,
        "expectations": exp,
        "current_conditions": float(icc.iloc[-1]) if not icc.empty else None,
        "expectations_change_3m": exp_ch,
        "sentiment_change_3m": cur_ch,
        "zone": zone,
    }
    high = float(ics.iloc[-12:].max())
    if high - cur >= 15:
        sig.flags.append(f"Falling sharply from a recent high ({high:.1f} within 12 months).")
    base = (
        f"Sentiment {cur:.1f} ({zone.lower()}, {fmt(cur_ch, 1, True)} in 3m); Expectations {exp:.1f} "
        f"({fmt(exp_ch, 1, True)} in 3m)"
    )
    several = int(p["umich_several"])
    if exp_ch is not None and exp_ch <= p["umich_expectations_drop"]:
        return sig.set(
            -1, "Expectations falling", f"{base}: expectations, the part that matters most, are falling fast."
        )
    if len(ics) >= several and (ics.iloc[-several:] < p["umich_pessimistic"]).all():
        return sig.set(
            -1, "Pessimistic", f"{base}: below 70 for {several}+ months, consumers are pessimistic."
        )
    if cur > p["umich_optimistic"] and cur_ch is not None and cur_ch >= 0:
        return sig.set(1, "Optimistic", f"{base}: above 80 and not falling, consumers are optimistic.")
    return sig.set(0, zone, f"{base}.")


def permits(v: View, p: dict) -> Signal:
    sig = Signal(
        "permits",
        "Building permits",
        BLOCK,
        "12-month average of YoY growth > 0 and rising -> +1; YoY < 0 and the 12-month average falling -> -1; "
        "else 0 (rising/falling over 3 months).",
        ["fred/PERMIT"],
    )
    s = v.series("fred/PERMIT")
    if why := v.stale("fred/PERMIT", s):
        return sig.awaiting(why)
    yoy = yoy_monthly(s)
    ma = yoy.rolling(12).mean().dropna()
    if len(ma) < 4:
        return sig.awaiting("not enough permits history")
    level, cur_yoy, cur_ma = float(s.iloc[-1]), float(yoy.iloc[-1]), float(ma.iloc[-1])
    ma_then = months_back(ma, 3)
    rising = ma_then is not None and cur_ma > ma_then
    falling = ma_then is not None and cur_ma < ma_then
    sig.as_of, sig.revised = iso(s.index[-1])[:7], "fred/PERMIT" in v.revised
    sig.percentile_10y = pct_rank(window(s, p["percentile_years"]), level)
    sig.metrics = {"level_k": level, "yoy_pct": cur_yoy, "yoy_12m_avg": cur_ma, "yoy_12m_avg_3m_ago": ma_then}
    if level >= p["permits_peak"]:
        sig.flags.append("Above 2.0m: peak territory (2004-06).")
    elif level <= p["permits_trough"]:
        sig.flags.append("At trough levels (<= 800k).")
    elif level < p["permits_trend_low"]:
        sig.flags.append("Below the long-run trend band of 1.3-1.4m.")
    base = (
        f"Permits {level:,.0f}k SAAR, {cur_yoy:+.1f}% YoY; 12-month average of YoY {cur_ma:+.1f}% "
        f"({'rising' if rising else 'falling' if falling else 'flat'} vs 3 months ago)"
    )
    if cur_ma > 0 and rising:
        return sig.set(1, "Growing", f"{base}: housing activity is accelerating.")
    if cur_yoy < 0 and falling:
        return sig.set(-1, "Shrinking", f"{base}: permits are falling, often ahead of weaker GDP.")
    return sig.set(0, "Mixed", f"{base}.")


NFIB_LEADING = [
    "plans_employment",
    "good_time_to_expand",
    "plans_inventories",
    "expect_economy_improve",
    "expect_real_sales_higher",
]


def nfib(v: View, p: dict) -> Signal:
    sig = Signal(
        "nfib",
        "NFIB small business optimism + ITPM leading index",
        BLOCK,
        "Optimism > 100 and the ITPM leading index (average of 5 leading components) above its 4-month average -> "
        "+1; optimism <= 95, or the ITPM index below its 4-month average and falling for 3 months -> -1; else 0.",
        ["manual/nfib_sbet"],
    )
    opt = v.manual("nfib_sbet", "optimism_index")
    if why := v.manual_stale("nfib_sbet", "optimism_index", opt):
        return sig.awaiting(why)
    parts = pd.concat([v.manual("nfib_sbet", c) for c in NFIB_LEADING], axis=1).dropna()
    ma_n, fall_n = int(p["nfib_ma_months"]), int(p["nfib_falling_months"])
    if len(parts) < ma_n + fall_n or parts.index[-1] != opt.index[-1]:
        return sig.awaiting("not enough months of the five leading components")
    custom = parts.mean(axis=1)
    ma = custom.rolling(ma_n).mean()
    cur, cur_ma, comp = float(custom.iloc[-1]), float(ma.iloc[-1]), float(opt.iloc[-1])
    diffs = custom.diff().iloc[-fall_n:]
    falling = bool((diffs < 0).all())
    trends = {}
    for c in NFIB_LEADING:
        s = v.manual("nfib_sbet", c).diff().dropna()
        if s.empty:
            continue
        up = s.iloc[-1] > 0
        n = 0
        for d in reversed(s.to_numpy()):
            if d == 0 or (d > 0) != up:
                break
            n += 1
        trends[c] = {"months": n, "direction": "up" if up else "down"}
    sig.as_of, sig.percentile_10y = iso(opt.index[-1])[:7], pct_rank(window(opt, p["percentile_years"]), comp)
    sig.metrics = {
        "optimism_index": comp,
        "itpm_index": cur,
        "itpm_4m_avg": cur_ma,
        "itpm_falling_3m": falling,
        "component_trends": trends,
    }
    base = (
        f"Optimism {comp:.1f}; ITPM leading index {cur:+.1f} vs 4-month average {cur_ma:+.1f}"
        f"{', falling 3 months in a row' if falling else ''}"
    )
    if comp > p["nfib_strong"] and cur > cur_ma:
        return sig.set(1, "Strong", f"{base}: above 100 with leading components improving.")
    if comp <= p["nfib_weak"]:
        return sig.set(-1, "Weak", f"{base}: at or below 95, historically zero growth or contraction.")
    if cur < cur_ma and falling:
        return sig.set(-1, "Leading index falling", f"{base}: the leading components are deteriorating.")
    note = " Below 100 is a warning." if comp < p["nfib_strong"] else ""
    return sig.set(0, "Neutral", f"{base}.{note}")


SIGNALS = [ism_manufacturing, ism_services, umich, permits, nfib]
