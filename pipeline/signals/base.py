"""The signal result shape and small time-series helpers shared by every rule."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class Signal:
    id: str
    name: str
    block: str
    rule: str  # one-line statement of the first-reading rule
    sources: list[str]
    score: int | None = None  # +1 / 0 / -1; None when awaiting data
    state: str = "Awaiting data"
    reason: str = ""  # reason_en: plain-English explanation shown next to the score
    as_of: str | None = None  # date of the latest observation used
    percentile_10y: float | None = None
    status: str = "awaiting"  # ok | awaiting
    metrics: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    revised: bool = False  # used revised data because no real-time vintage existed for that day

    def awaiting(self, why: str) -> Signal:
        self.score, self.status, self.state = None, "awaiting", "Awaiting data"
        self.reason = f"Awaiting data: {why}. Left out of the score."
        return self

    def set(self, score: int, state: str, reason: str) -> Signal:
        self.score, self.state, self.reason, self.status = int(score), state, reason, "ok"
        return self

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "block": self.block,
            "score": self.score,
            "state": self.state,
            "reason_en": self.reason,
            "as_of": self.as_of,
            "percentile_10y": None if self.percentile_10y is None else round(self.percentile_10y, 1),
            "status": self.status,
            "metrics": {k: _round(v) for k, v in self.metrics.items()},
            "flags": self.flags,
            "rule": self.rule,
            "sources": self.sources,
            "revised": self.revised,
        }


def _round(v: Any) -> Any:
    if isinstance(v, float | np.floating):
        return None if np.isnan(v) else round(float(v), 3)
    if isinstance(v, np.integer):
        return int(v)
    return v


def iso(ts: pd.Timestamp) -> str:
    return ts.date().isoformat()


def value_at(s: pd.Series, when: pd.Timestamp) -> float | None:
    """Last value on or before ``when``."""
    sub = s[s.index <= when]
    return None if sub.empty else float(sub.iloc[-1])


def change(s: pd.Series, days: int) -> float | None:
    """Latest value minus the value ``days`` calendar days before the latest observation."""
    before = value_at(s, s.index[-1] - pd.Timedelta(days=days))
    return None if before is None else float(s.iloc[-1]) - before


def pct_change(s: pd.Series, days: int) -> float | None:
    before = value_at(s, s.index[-1] - pd.Timedelta(days=days))
    return None if not before else (float(s.iloc[-1]) / before - 1) * 100


def window(s: pd.Series, years: float) -> pd.Series:
    return s[s.index > s.index[-1] - pd.DateOffset(years=int(years))]


def pct_rank(values: pd.Series | np.ndarray, x: float) -> float | None:
    """Percentile of ``x`` within ``values`` (0-100, share of values at or below ``x``)."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return None
    return float((arr <= x).mean() * 100)


def monthly(s: pd.Series) -> pd.Series:
    """Monthly series on month-start dates; a daily series becomes its monthly mean."""
    return s.resample("MS").mean().dropna()


def months_back(s: pd.Series, n: int) -> float | None:
    """Value ``n`` months before the latest month of a monthly series."""
    target = s.index[-1] - pd.DateOffset(months=n)
    return None if target not in s.index else float(s[target])


def yoy_monthly(s: pd.Series) -> pd.Series:
    """Year-on-year % change of a monthly series (month-start index)."""
    prev = s.reindex(s.index - pd.DateOffset(months=12)).to_numpy()
    return pd.Series((s.to_numpy() / prev - 1) * 100, index=s.index).dropna()


def streak(s: pd.Series, level: float) -> tuple[int, str, bool]:
    """Consecutive latest months on the same side of ``level``: (months, "above"/"below", reached start)."""
    above = s.iloc[-1] >= level
    n = 0
    for v in reversed(s.to_numpy()):
        if (v >= level) != above:
            return n, "above" if above else "below", False
        n += 1
    return n, "above" if above else "below", True


def ordinal(x: float | None) -> str:
    """Percentile as an English ordinal: 2 -> '2nd', 11 -> '11th', None -> 'n/a'."""
    if x is None:
        return "n/a"
    n = int(round(x))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def fmt(x: float | None, digits: int = 1, sign: bool = False) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}"
