"""Builders for hand-made point-in-time libraries used by the signal tests."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from pipeline.config import SIGNALS
from pipeline.manual.schemas import MANUAL_FILES
from pipeline.signals.data import Library, ManualSource, SeriesSource

TODAY = date(2026, 10, 21)
P = dict(SIGNALS)


def daily(points: list[tuple[str, float]], end: str = "2026-10-20") -> pd.Series:
    """Business-day series interpolated linearly between (date, value) anchors, up to ``end``."""
    anchors = pd.Series({pd.Timestamp(d): v for d, v in points}).sort_index()
    idx = pd.bdate_range(anchors.index[0], end)
    return anchors.reindex(anchors.index.union(idx)).interpolate("time").reindex(idx)


def monthly(values: list[float], last: str = "2026-09") -> pd.Series:
    idx = pd.date_range(end=pd.Timestamp(f"{last}-01"), periods=len(values), freq="MS")
    return pd.Series(values, index=idx, dtype=float)


def noisy(n: int, level: float, amp: float, seed: int = 1) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(level + amp * rng.standard_normal(n))


def library(
    series: dict[str, tuple[pd.Series, str]] | None = None,
    manual: dict[str, pd.DataFrame] | None = None,
    today: date = TODAY,
    vintages: dict[str, list[list[str]]] | None = None,
    max_age: dict[str, int] | None = None,
) -> Library:
    lib = Library(today=today)
    for key, (s, freq) in (series or {}).items():
        vint = None
        if vintages and key in vintages:
            arr = np.array(vintages[key], dtype=str)
            vint = (
                arr[:, 0],
                arr[:, 1],
                arr[:, 2],
                pd.to_numeric(pd.Series(arr[:, 3]), errors="coerce").to_numpy(),
            )
        default_age = {"daily": 10, "weekly": 21, "monthly": 100}.get(freq, 250)
        lib.series[key] = SeriesSource(
            key, key.split("/")[0], freq, (max_age or {}).get(key, default_age), s, vint
        )
    specs = {f.name: f for f in MANUAL_FILES}
    for name, frame in (manual or {}).items():
        spec = specs[name]
        rules = {t.column: t.release for t in spec.tracked}
        rules["*"] = spec.tracked[0].release
        lib.manual[name] = ManualSource(name, frame.astype(float), rules)
    return lib


def frame(columns: dict[str, list[float]], last: str = "2026-09") -> pd.DataFrame:
    n = len(next(iter(columns.values())))
    idx = pd.date_range(end=pd.Timestamp(f"{last}-01"), periods=n, freq="MS")
    return pd.DataFrame(columns, index=idx, dtype=float)
