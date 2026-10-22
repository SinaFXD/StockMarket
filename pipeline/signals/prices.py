"""Cyclical prices, the dollar and the equity trend (lesson 12; S&P trend rule proposed in docs/02)."""

from __future__ import annotations

from .base import Signal, fmt, iso, pct_change, pct_rank, window, yoy_monthly
from .data import View

BLOCK = "prices_fx_equities"


def _yoy(v: View, key: str) -> tuple[float | None, str | None]:
    s = v.series(key)
    if s.empty:
        return None, None
    if v.lib.series[key].frequency in ("daily", "weekly"):
        return pct_change(s, 365), iso(s.index[-1])
    y = yoy_monthly(s)
    return (float(y.iloc[-1]), iso(y.index[-1])[:7]) if not y.empty else (None, None)


def _commodity(sig_id: str, name: str, keys: list[str]):
    def rule(v: View, p: dict) -> Signal:
        sig = Signal(
            sig_id,
            name,
            BLOCK,
            "YoY > +5% -> +1; YoY < -5% -> -1; else 0. Judge demand- vs supply-driven moves yourself (override).",
            keys,
        )
        key, s = v.freshest(keys)
        if why := v.stale(key, s):
            return sig.awaiting(why)
        yoy, as_of = _yoy(v, key)
        if yoy is None:
            return sig.awaiting("less than a year of history")
        lim = p["commodity_yoy_pct"]
        sig.as_of, sig.sources, sig.revised = as_of, [key], key in v.revised
        sig.percentile_10y = pct_rank(window(s, p["percentile_years"]), float(s.iloc[-1]))
        sig.metrics = {"level": float(s.iloc[-1]), "yoy_pct": yoy}
        base = f"{name} {s.iloc[-1]:,.2f} ({yoy:+.1f}% YoY)"
        if yoy > lim:
            return sig.set(1, "Rising", f"{base}: rising prices, if demand-driven a sign of stronger growth.")
        if yoy < -lim:
            return sig.set(-1, "Falling", f"{base}: falling prices point to weaker demand.")
        return sig.set(0, "Flat", f"{base}: no clear trend.")

    rule.__name__ = sig_id
    return rule


brent = _commodity("brent", "Brent crude", ["fred/DCOILBRENTEU", "yahoo/BZ_F"])
copper = _commodity("copper", "Copper", ["yahoo/HG_F", "fred/PCOPPUSDM"])
iron_ore = _commodity("iron_ore", "Iron ore", ["fred/PIORECRUSDM"])
lumber = _commodity("lumber", "Lumber (PPI)", ["fred/WPU081"])


def dollar(v: View, p: dict) -> Signal:
    sig = Signal(
        "dollar",
        "US dollar (broad, trade-weighted)",
        BLOCK,
        "YoY > +5% -> -1 (deflationary headwind); YoY < -5% -> +1; else 0.",
        ["fred/DTWEXBGS"],
    )
    s = v.series("fred/DTWEXBGS")
    if why := v.stale("fred/DTWEXBGS", s):
        return sig.awaiting(why)
    yoy = pct_change(s, 365)
    if yoy is None or (s.index[-1] - s.index[0]).days < 365:
        return sig.awaiting("less than a year of history")
    lim = p["dollar_yoy_pct"]
    sig.as_of, sig.percentile_10y = (
        iso(s.index[-1]),
        pct_rank(window(s, p["percentile_years"]), float(s.iloc[-1])),
    )
    sig.metrics = {"index": float(s.iloc[-1]), "yoy_pct": yoy}
    base = f"Broad dollar index {s.iloc[-1]:.1f} ({yoy:+.1f}% YoY)"
    if yoy > lim:
        return sig.set(
            -1, "Strong dollar", f"{base}: a strong dollar is deflationary for USD-priced commodities."
        )
    if yoy < -lim:
        return sig.set(1, "Weak dollar", f"{base}: a weaker dollar supports commodities and global growth.")
    return sig.set(0, "Stable", f"{base}.")


def sp500(v: View, p: dict) -> Signal:
    sig = Signal(
        "sp500",
        "S&P 500 trend",
        BLOCK,
        "Above its 200-day average and up over 3 months -> +1; below and down -> -1; else 0 (proposed rule, tune).",
        ["yahoo/GSPC"],
    )
    s = v.series("yahoo/GSPC")
    if why := v.stale("yahoo/GSPC", s):
        return sig.awaiting(why)
    n = int(p["sp500_ma_days"])
    if len(s) < n:
        return sig.awaiting("not enough history")
    last, ma = float(s.iloc[-1]), float(s.iloc[-n:].mean())
    ch = pct_change(s, p["lookback_days"])
    sig.as_of, sig.percentile_10y = iso(s.index[-1]), pct_rank(window(s, p["percentile_years"]), last)
    sig.metrics = {"close": last, "ma_200d": ma, "vs_ma_pct": (last / ma - 1) * 100, "change_3m_pct": ch}
    base = f"S&P 500 {last:,.0f}, {(last / ma - 1) * 100:+.1f}% vs its 200-day average, {fmt(ch, 1, True)}% over 3 months"
    if last > ma and ch is not None and ch > 0:
        return sig.set(1, "Uptrend", f"{base}: prices are discounting a better future.")
    if last < ma and ch is not None and ch < 0:
        return sig.set(-1, "Downtrend", f"{base}: prices are discounting a weaker future.")
    return sig.set(0, "Mixed", f"{base}.")


SIGNALS = [brent, copper, iron_ore, lumber, dollar, sp500]
