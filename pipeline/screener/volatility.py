"""Volatility for the screener's filter (lessons 22-29: realised and implied volatility roughly >= 1.5x VIX) and
for the trade-idea template's expected move.

- Realised: annualised standard deviation of daily log returns over ~3 months, and the average true range
  (ATR) in % of the price, from one batch price download for the whole universe.
- Implied: at-the-money options of the expiry closest to 45 days. Yahoo's own ``impliedVolatility`` field is
  unusable outside market hours (bid and ask are zero), so the volatility is backed out of the option prices
  with Black-Scholes: the mid price when there is a quote, else the last trade.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from ..http import FetchError


def realised(frame: pd.DataFrame, days: int, atr_days: int) -> dict[str, float | None]:
    """``frame``: one stock's daily High/Low/Close (oldest first)."""
    close = frame["Close"].dropna()
    if len(close) < days // 2:
        return {"rv": None, "atr": None}
    rets = np.log(close).diff().dropna().iloc[-days:]
    rv = float(rets.std(ddof=1) * math.sqrt(252) * 100) if len(rets) > 5 else None
    hi, lo, prev = frame["High"], frame["Low"], frame["Close"].shift(1)
    tr = pd.concat([hi - lo, (hi - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1).dropna()
    atr = float(tr.iloc[-atr_days:].mean() / close.iloc[-1] * 100) if len(tr) >= atr_days else None
    return {"rv": rv, "atr": atr}


def download_prices(
    symbols: list[str], chunk: int, download: Callable | None = None
) -> dict[str, pd.DataFrame]:
    """Two years of daily bars per symbol, in batches (``yfinance.download``): ~3 months for the realised
    volatility, the rest for the trade-idea chart (200-day average, 52-week range) and the Portfolio Lab."""
    if download is None:
        import yfinance as yf

        def download(batch):
            return yf.download(
                batch,
                period="2y",
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=True,
            )

    out: dict[str, pd.DataFrame] = {}
    for i in range(0, len(symbols), chunk):
        batch = symbols[i : i + chunk]
        df = download(batch)
        if df is None or df.empty:
            continue
        for sym in batch:
            try:
                sub = df[sym] if isinstance(df.columns, pd.MultiIndex) else df
            except KeyError:
                continue
            if not sub.dropna(how="all").empty:
                out[sym] = sub.dropna(how="all")
    return out


def compact_bars(frame: pd.DataFrame, n: int) -> dict[str, list]:
    """The last ``n`` daily bars as columns (dates, open, high, low, close, volume) for the price chart."""
    f = frame.dropna(subset=["Close"]).iloc[-n:]

    def col(name: str) -> list:
        if name not in f:
            return [None] * len(f)
        vals = f[name].astype(float).tolist()
        return [None if v != v else (round(v, 2) if abs(v) >= 10 else round(v, 4)) for v in vals]

    vol = f["Volume"].tolist() if "Volume" in f else [None] * len(f)
    return {
        "d": [i.date().isoformat() for i in f.index],
        "o": col("Open"),
        "h": col("High"),
        "l": col("Low"),
        "c": col("Close"),
        "v": [None if v is None or v != v else int(v) for v in vol],
    }


# -- implied volatility ------------------------------------------------------------------------------------
def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_price(spot: float, strike: float, t: float, r: float, vol: float, call: bool) -> float:
    if vol <= 0 or t <= 0:
        return max(0.0, (spot - strike) if call else (strike - spot))
    d1 = (math.log(spot / strike) + (r + vol * vol / 2) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    if call:
        return spot * _norm_cdf(d1) - strike * math.exp(-r * t) * _norm_cdf(d2)
    return strike * math.exp(-r * t) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def implied_vol(price: float, spot: float, strike: float, t: float, r: float, call: bool) -> float | None:
    """Black-Scholes implied volatility by bisection (None when the price is below intrinsic value)."""
    lo, hi = 0.01, 5.0
    if not price or price <= 0 or bs_price(spot, strike, t, r, lo, call) > price:
        return None
    if bs_price(spot, strike, t, r, hi, call) < price:
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if bs_price(spot, strike, t, r, mid, call) > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def _option_price(row: dict[str, Any]) -> float | None:
    bid, ask, last = row.get("bid") or 0, row.get("ask") or 0, row.get("lastPrice") or 0
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return last or None


def atm_iv(spot: float, calls: list[dict], puts: list[dict], t: float, r: float, n: int = 2) -> float | None:
    """Average implied volatility (in %) of the ``n`` strikes closest to the spot, calls and puts."""
    vols = []
    for rows, call in ((calls, True), (puts, False)):
        for row in sorted(rows, key=lambda x: abs(x["strike"] - spot))[:n]:
            p = _option_price(row)
            v = implied_vol(p, spot, row["strike"], t, r, call) if p else None
            if v is not None:
                vols.append(v)
    return round(float(np.median(vols)) * 100, 2) if vols else None


def fetch_iv(
    symbol: str, spot: float, today: date, target_days: int, r: float, ticker=None
) -> dict[str, Any]:
    """The expiry closest to ``target_days`` and its at-the-money implied volatility."""
    if ticker is None:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
    expiries = list(ticker.options or [])
    if not expiries:  # Yahoo answers an empty list when it throttles: retry next run rather than cache it
        raise FetchError(f"no option expiries for {symbol}")
    future = [e for e in expiries if (date.fromisoformat(e) - today).days >= 7]
    if not future:
        return {"iv": None, "expiry": None}
    expiry = min(future, key=lambda e: abs((date.fromisoformat(e) - today).days - target_days))
    chain = ticker.option_chain(expiry)
    t = (date.fromisoformat(expiry) - today).days / 365
    calls = chain.calls[["strike", "bid", "ask", "lastPrice"]].to_dict("records")
    puts = chain.puts[["strike", "bid", "ask", "lastPrice"]].to_dict("records")
    return {"iv": atm_iv(spot, calls, puts, t, r), "expiry": expiry}
