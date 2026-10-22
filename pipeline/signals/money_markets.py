"""US money markets (lessons 4-6 and VIX): curve, real rate, credit spreads, M2, VIX."""

from __future__ import annotations

import pandas as pd

from .base import Signal, change, fmt, iso, monthly, ordinal, pct_rank, value_at, window, yoy_monthly
from .data import View

BLOCK = "money_markets"


def curve(v: View, p: dict) -> Signal:
    sig = Signal(
        "curve",
        "Yield curve (10y-2y)",
        BLOCK,
        "Inverted -> -1. Flat (0-0.5pp): flattening -> -1, steepening -> +1. Normal and steepening -> +1. "
        "Change measured over 3 months.",
        ["fred/T10Y2Y", "fred/T10Y3M"],
    )
    s = v.series("fred/T10Y2Y")
    if why := v.stale("fred/T10Y2Y", s):
        return sig.awaiting(why)
    cur, ch = float(s.iloc[-1]), change(s, p["lookback_days"])
    band, flat = p["curve_stable_band"], p["curve_flat_max"]
    sig.as_of, sig.metrics = iso(s.index[-1]), {"spread_10y2y": cur, "change_3m": ch}
    sig.percentile_10y = pct_rank(window(s, p["percentile_years"]), cur)
    direction = "stable"
    if ch is not None and abs(ch) > band:
        direction = "steepening" if ch > 0 else "flattening"
    base = f"10y-2y is {cur:+.2f}pp ({fmt(ch, 2, True)}pp over 3 months, {direction})"
    if cur < 0:
        sig.set(-1, "Inverted", f"{base}: the curve is inverted, the market is pricing a contraction.")
    elif cur <= flat:
        if direction == "flattening":
            sig.set(-1, "Flat & flattening", f"{base}: a flat curve moving toward inversion is bearish.")
        elif direction == "steepening":
            sig.set(1, "Flat & steepening", f"{base}: steepening out of a flat curve is bullish.")
        else:
            sig.set(0, "Flat", f"{base}: a flat curve signals a transition; wait for the direction.")
    elif direction == "steepening":
        sig.set(1, "Normal & steepening", f"{base}: an upward-sloping, steepening curve expects expansion.")
    else:
        sig.set(0, "Normal", f"{base}: a normal curve, no transition under way.")
    short = v.series("fred/T10Y3M")
    if not short.empty and v.stale("fred/T10Y3M", short) is None:
        sig.metrics["spread_10y3m"] = float(short.iloc[-1])
        if short.iloc[-1] < 0 <= cur:
            sig.flags.append(
                f"Short end inverted: 10y-3m is {short.iloc[-1]:+.2f}pp while 10y-2y is positive (as in Feb 2020)."
            )
    return sig


def real_rate(v: View, p: dict) -> Signal:
    sig = Signal(
        "real_rate",
        "Real 10y rate (10y - CPI YoY)",
        BLOCK,
        "Percentile vs last 10 years <= 25th -> +1 (abundant liquidity); >= 75th and rising over 3 months -> -1.",
        ["fred/DGS10", "fred/CPIAUCSL"],
    )
    y, cpi = v.series("fred/DGS10"), v.series("fred/CPIAUCSL")
    if why := v.stale("fred/DGS10", y) or v.stale("fred/CPIAUCSL", cpi):
        return sig.awaiting(why)
    infl = yoy_monthly(cpi)
    if len(infl) < 24:
        return sig.awaiting("not enough CPI history")
    real_m = (monthly(y) - infl).dropna()
    cur = float(y.iloc[-1]) - float(infl.iloc[-1])
    # three months earlier: the yield then minus the inflation print that was latest then
    y_then = value_at(y, y.index[-1] - pd.Timedelta(days=p["lookback_days"]))
    infl_then = value_at(infl, infl.index[-1] - pd.DateOffset(months=3))
    then = None if y_then is None or infl_then is None else y_then - infl_then
    rising = then is not None and cur > then
    pct = pct_rank(window(real_m, p["percentile_years"]), cur)
    sig.as_of, sig.percentile_10y = iso(y.index[-1]), pct
    sig.metrics = {
        "real_rate": cur,
        "yield_10y": float(y.iloc[-1]),
        "cpi_yoy": float(infl.iloc[-1]),
        "cpi_month": iso(infl.index[-1])[:7],
        "real_rate_3m_ago": then,
    }
    sig.revised = "fred/CPIAUCSL" in v.revised
    base = (
        f"Real 10y = {y.iloc[-1]:.2f}% yield - {infl.iloc[-1]:.1f}% CPI YoY = {cur:+.2f}% "
        f"({ordinal(pct)} percentile of 10 years, {'rising' if rising else 'not rising'} over 3 months)"
    )
    if pct is not None and pct <= p["real_rate_low_pct"]:
        sig.set(1, "Low vs history", f"{base}: liquidity is abundant relative to history (supports P/E).")
    elif pct is not None and pct >= p["real_rate_high_pct"] and rising:
        sig.set(-1, "High & rising", f"{base}: liquidity is getting scarce relative to history.")
    else:
        sig.set(
            0, "Mid-range" if pct is None or pct < p["real_rate_high_pct"] else "High, not rising", f"{base}."
        )
    return sig


CREDIT = [("CCC", "fred/BAMLH0A3HYC"), ("BBB", "fred/BAMLC0A4CBBB"), ("AA", "fred/BAMLC0A2CAA")]


def _three_month_changes(s: pd.Series, days: int) -> pd.Series:
    prev = s.reindex(s.index - pd.Timedelta(days=days), method="ffill")
    return pd.Series(s.to_numpy() - prev.to_numpy(), index=s.index).dropna()


def credit(v: View, p: dict) -> Signal:
    sig = Signal(
        "credit",
        "Corporate credit spreads (CCC / BBB / AA)",
        BLOCK,
        "Each spread: 3-month change above its 90th percentile -> -1, below its 10th -> +1. Combined: two agree, "
        "or CCC widening alone ('junk moves first') -> -1. Moody's Baa-10y when ICE history is too short.",
        [k for _, k in CREDIT] + ["fred/BAA10Y"],
    )
    days, years = p["lookback_days"], p["percentile_years"]
    parts: dict[str, int] = {}
    for label, key in CREDIT:
        s = v.series(key)
        if v.stale(key, s) or s.empty:
            continue
        ch = _three_month_changes(window(s, years), days)
        if ch.empty or (ch.index[-1] - ch.index[0]).days < p["credit_min_history_days"]:
            continue
        pct = pct_rank(ch, float(ch.iloc[-1]))
        parts[label] = -1 if pct >= p["credit_wide_pct"] else 1 if pct <= p["credit_tight_pct"] else 0
        sig.metrics[f"{label.lower()}_oas"] = float(s.iloc[-1])
        sig.metrics[f"{label.lower()}_change_3m"] = float(ch.iloc[-1])
        sig.metrics[f"{label.lower()}_change_pct"] = pct
        sig.as_of = iso(s.index[-1])
    if len(parts) == 3:
        ccc = v.series("fred/BAMLH0A3HYC")
        sig.percentile_10y = pct_rank(window(ccc, years), float(ccc.iloc[-1]))
        detail = ", ".join(
            f"{k} {sig.metrics[k.lower() + '_oas']:.2f}% ({sig.metrics[k.lower() + '_change_3m']:+.2f}pp in 3m, "
            f"{ordinal(sig.metrics[k.lower() + '_change_pct'])} pct of 3m changes)"
            for k in parts
        )
        total = sum(parts.values())
        if parts["CCC"] == -1 and parts["BBB"] != -1 and parts["AA"] != -1:
            sig.flags.append("Junk moves first: CCC is widening fast while BBB and AA have not followed yet.")
            return sig.set(
                -1, "Junk widening first", f"{detail}. CCC is widening unusually fast: junk moves first."
            )
        if total <= -2:
            return sig.set(
                -1, "Widening", f"{detail}. Spreads are widening: credit is pricing more default risk."
            )
        if total >= 2:
            return sig.set(1, "Tightening", f"{detail}. Spreads are tightening: credit is relaxed.")
        return sig.set(0, "Stable", f"{detail}. No unusual move in spreads.")
    # long-history fallback (ICE data on FRED only starts in 2023)
    s = v.series("fred/BAA10Y")
    if why := v.stale("fred/BAA10Y", s):
        return sig.awaiting(why)
    ch = _three_month_changes(window(s, years), days)
    pct = pct_rank(ch, float(ch.iloc[-1]))
    sig.metrics = {"baa_10y": float(s.iloc[-1]), "baa_change_3m": float(ch.iloc[-1]), "baa_change_pct": pct}
    sig.as_of, sig.percentile_10y = iso(s.index[-1]), pct_rank(window(s, years), float(s.iloc[-1]))
    sig.flags.append(
        "Using Moody's Baa-10y (long history): ICE CCC/BBB/AA spreads are not available for this date."
    )
    detail = (
        f"Baa-10y spread {s.iloc[-1]:.2f}pp ({ch.iloc[-1]:+.2f}pp in 3m, {ordinal(pct)} pct of 3m changes)"
    )
    if pct >= p["credit_wide_pct"]:
        return sig.set(-1, "Widening", f"{detail}: spreads are widening unusually fast.")
    if pct <= p["credit_tight_pct"]:
        return sig.set(1, "Tightening", f"{detail}: spreads are tightening unusually fast.")
    return sig.set(0, "Stable", f"{detail}: no unusual move.")


def m2(v: View, p: dict) -> Signal:
    sig = Signal(
        "m2",
        "M2 money supply",
        BLOCK,
        "Month-on-month growth in the top 5% of months since 1959 -> +1 (abnormal liquidity injection); "
        "YoY < 0 -> -1; else 0. Read as confirmation of the bond-market signals.",
        ["fred/M2SL"],
    )
    s = v.series("fred/M2SL")
    if why := v.stale("fred/M2SL", s):
        return sig.awaiting(why)
    mom = (s.pct_change() * 100).dropna()
    yoy = yoy_monthly(s)
    if len(mom) < 60 or yoy.empty:
        return sig.awaiting("not enough M2 history")
    cur, cur_yoy = float(mom.iloc[-1]), float(yoy.iloc[-1])
    top = float(mom.quantile(p["m2_injection_pct"] / 100))
    mean, sd = float(mom.mean()), float(mom.std())
    sig.as_of, sig.revised = iso(s.index[-1]), "fred/M2SL" in v.revised
    sig.percentile_10y = pct_rank(window(mom, p["percentile_years"]), cur)
    sig.metrics = {
        "mom_pct": cur,
        "yoy_pct": cur_yoy,
        "mom_mean": mean,
        "mom_sd": sd,
        "mom_top5": top,
        "mom_sigma": (cur - mean) / sd if sd else None,
    }
    base = (
        f"M2 {cur:+.2f}% MoM ({(cur - mean) / sd:+.1f} sigma vs the {mean:.2f}% average since 1959), "
        f"{cur_yoy:+.1f}% YoY"
    )
    if cur >= top:
        return sig.set(1, "Abnormal injection", f"{base}: top-5% month, the Fed is injecting liquidity.")
    if cur_yoy < 0:
        return sig.set(-1, "Shrinking", f"{base}: money supply is contracting, liquidity is being withdrawn.")
    return sig.set(0, "Normal growth", f"{base}: within the normal range.")


def vix(v: View, p: dict) -> Signal:
    sig = Signal(
        "vix",
        "VIX",
        BLOCK,
        "Percentile vs 10 years >= 75th and up over 3 months -> -1; <= 25th -> +1; else 0.",
        ["fred/VIXCLS", "yahoo/VIX"],
    )
    key, s = v.freshest(["fred/VIXCLS", "yahoo/VIX"])
    if why := v.stale(key, s):
        return sig.awaiting(why)
    cur, ch = float(s.iloc[-1]), change(s, p["lookback_days"])
    pct = pct_rank(window(s, p["percentile_years"]), cur)
    sig.as_of, sig.percentile_10y, sig.sources = iso(s.index[-1]), pct, [key]
    sig.metrics = {"vix": cur, "change_3m": ch}
    base = f"VIX {cur:.1f} ({ordinal(pct)} percentile of 10 years, {fmt(ch, 1, True)} over 3 months)"
    if pct is not None and pct >= p["vix_high_pct"] and ch is not None and ch > 0:
        return sig.set(-1, "High & rising", f"{base}: volatility is high and rising.")
    if pct is not None and pct <= p["vix_low_pct"]:
        return sig.set(1, "Low", f"{base}: calm markets, cheap volatility.")
    return sig.set(0, "Normal", f"{base}.")


SIGNALS = [curve, real_rate, credit, m2, vix]
