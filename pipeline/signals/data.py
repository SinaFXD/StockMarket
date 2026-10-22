"""Point-in-time data access: every signal sees only what was published on its "as of" day.

- FRED series with ALFRED vintages: the values as published on that day (``as_known_on``).
- Market prices (daily) are never revised: everything up to that day.
- Other monthly sources (UMich, Eurostat) are not revised much and have no vintages: a month counts as
  known from its last day (both publish the final number by then).
- Hand-entered reports: a month counts as known from its release date (``pipeline.manual.releases``).
- Before a series' ALFRED history starts, today's (revised) values are used with a publication lag, and the
  snapshot is flagged ``revised`` so the evidence page can say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..catalog import CatalogEntry, load_catalog
from ..config import MANUAL_GRACE_DAYS, RAW_DIR, SITE_DATA_DIR
from ..health import max_age_days
from ..manual import MANUAL_FILES, load_all
from ..manual.releases import ReleaseRule, add_months, month_of
from ..store import RawCache, read_series

# Without vintages, a monthly FRED value is assumed public this many days after its month ends.
FRED_MONTHLY_LAG_DAYS = 45


def _to_series(rows: list[list], column: int = 1) -> pd.Series:
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows])
    vals = pd.to_numeric(pd.Series([r[column] for r in rows], index=idx), errors="coerce")
    return vals.dropna().sort_index()


@dataclass
class SeriesSource:
    key: str
    source: str
    frequency: str
    max_age: int
    current: pd.Series
    vintages: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None  # date, start, end, value


@dataclass
class ManualSource:
    name: str
    frame: pd.DataFrame  # index: month start (Timestamp), columns: values
    rules: dict[str, ReleaseRule]  # release rule per column ("*" = default)


@dataclass
class Library:
    series: dict[str, SeriesSource] = field(default_factory=dict)
    manual: dict[str, ManualSource] = field(default_factory=dict)
    today: date = field(default_factory=date.today)

    @classmethod
    def load(
        cls,
        today: date,
        *,
        site_data_dir: Path = SITE_DATA_DIR,
        raw_dir: Path = RAW_DIR,
        manual_dir: Path | None = None,
        catalog: list[CatalogEntry] | None = None,
    ) -> Library:
        lib = cls(today=today)
        cache = RawCache(raw_dir)
        for entry in catalog or load_catalog():
            published = read_series(site_data_dir / "series" / entry.source / f"{entry.name}.json")
            if published is None:
                continue
            freq = published.meta.get("frequency") or "monthly"
            vint = None
            if entry.vintages and (hit := cache.load("alfred", entry.name)):
                rows = hit[0].get("rows") or []
                if rows:
                    arr = np.array(rows, dtype=str)
                    values = pd.to_numeric(pd.Series(arr[:, 3]), errors="coerce").to_numpy()
                    vint = (arr[:, 0], arr[:, 1], arr[:, 2], values)
            lib.series[entry.key] = SeriesSource(
                key=entry.key,
                source=entry.source,
                frequency=freq,
                max_age=max_age_days(entry, freq),
                current=_to_series(published.rows),
                vintages=vint,
            )
        kwargs = {"manual_dir": manual_dir} if manual_dir else {}
        for ds in load_all(today, **kwargs):
            cols = [c.name for c in ds.spec.columns if c.is_value]
            if not cols:
                continue
            frame = pd.DataFrame(
                [[r[c] for c in cols] for r in ds.rows],
                index=pd.to_datetime([f"{r['month']}-01" for r in ds.rows]),
                columns=cols,
                dtype=float,
            ).sort_index()
            rules = {t.column: t.release for t in ds.spec.tracked}
            if ds.spec.tracked:
                rules["*"] = ds.spec.tracked[0].release
                lib.manual[ds.spec.name] = ManualSource(ds.spec.name, frame, rules)
        return lib

    def view(self, as_of: date) -> View:
        return View(self, as_of)


class View:
    """The library as it looked at the end of ``as_of``."""

    def __init__(self, lib: Library, as_of: date) -> None:
        self.lib = lib
        self.as_of = as_of
        self.ts = pd.Timestamp(as_of)
        self.latest = as_of >= lib.today
        self.revised: set[str] = set()
        self._cache: dict[str, pd.Series] = {}

    # -- automatic series -------------------------------------------------------------------------------
    def series(self, key: str) -> pd.Series:
        if key in self._cache:
            return self._cache[key]
        src = self.lib.series.get(key)
        if src is None:
            out = pd.Series(dtype=float)
        elif self.latest:
            out = src.current
        else:
            out = self._point_in_time(src)
        self._cache[key] = out
        return out

    def _point_in_time(self, src: SeriesSource) -> pd.Series:
        day = self.as_of.isoformat()
        if src.vintages is not None:
            dates, start, end, values = src.vintages
            mask = (start <= day) & (end >= day) & ~np.isnan(values)
            if mask.any():
                return pd.Series(values[mask], index=pd.to_datetime(dates[mask])).sort_index()
            self.revised.add(src.key)  # before ALFRED coverage: fall through to the lag rule
        s = src.current
        if src.frequency in ("daily", "weekly"):
            known = s.index <= self.ts - pd.Timedelta(days=0 if src.frequency == "daily" else 6)
        elif src.frequency == "monthly":
            lag = 0 if src.source in ("umich", "eurostat") else FRED_MONTHLY_LAG_DAYS
            known = (s.index + pd.offsets.MonthEnd(0) + pd.Timedelta(days=lag)) <= self.ts
        else:  # quarterly / annual
            known = (s.index + pd.offsets.QuarterEnd(0) + pd.Timedelta(days=60)) <= self.ts
        if src.vintages is None and src.frequency not in ("daily", "weekly") and src.source == "fred":
            self.revised.add(src.key)
        return s[known]

    def stale(self, key: str, s: pd.Series | None = None) -> str | None:
        """``None`` when fresh, else a short explanation (no data, or last value too old)."""
        s = self.series(key) if s is None else s
        if s.empty:
            return "no data yet"
        src = self.lib.series[key]
        age = (self.ts - s.index[-1]).days  # same yardstick as the Data health page
        if age > src.max_age:
            return f"last value {s.index[-1].date().isoformat()} is {age} days old"
        return None

    def freshest(self, keys: list[str]) -> tuple[str, pd.Series]:
        """Of several sources for the same thing, the one with the most recent observation."""
        best = max(
            keys, key=lambda k: self.series(k).index[-1] if not self.series(k).empty else pd.Timestamp.min
        )
        return best, self.series(best)

    # -- hand-entered reports ---------------------------------------------------------------------------
    def manual(self, name: str, column: str) -> pd.Series:
        src = self.lib.manual.get(name)
        if src is None or column not in src.frame.columns:
            return pd.Series(dtype=float)
        s = src.frame[column].dropna()
        rule = src.rules.get(column, src.rules["*"])
        if not self.latest:
            known = [pd.Timestamp(rule.due_date(month_of(ts.date()))) <= self.ts for ts in s.index]
            s = s[known]
        return s

    def manual_stale(self, name: str, column: str, s: pd.Series | None = None) -> str | None:
        src = self.lib.manual.get(name)
        if src is None:
            return "no data entered yet"
        s = self.manual(name, column) if s is None else s
        if s.empty:
            return "no data entered yet"
        rule = src.rules.get(column, src.rules["*"])
        last = month_of(s.index[-1].date())
        expected = rule.latest_released_month(self.as_of)
        if last >= expected:
            return None
        missing = add_months(last, 1)
        due = rule.due_date(missing)
        if (self.as_of - due).days <= MANUAL_GRACE_DAYS:
            return None  # just released: still use the previous month for a few days
        return f"last entry {last}; the {missing} report has been out since {due.isoformat()}"


def month_ends(start: str, today: date) -> list[date]:
    """Last day of every month from ``start`` (YYYY-MM) up to the last complete month before ``today``."""
    out = []
    month = start
    while True:
        y, m = int(month[:4]), int(month[5:7])
        last = (date(y + (m == 12), m % 12 + 1, 1)) - timedelta(days=1)
        if last >= today:
            return out
        out.append(last)
        month = add_months(month, 1)


__all__ = ["Library", "View", "month_ends", "MANUAL_FILES"]
