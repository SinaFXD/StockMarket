"""Run the forward test of the Screener's types after the screener: add this week's cohort, fill the returns that
are due, write ``site/data/forward/outliers.csv`` and ``summary.json``."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..store import _atomic_write_text, iso, read_series, utc_now, write_json
from ..workbench.stock import SECTOR_ETF
from . import outliers

log = logging.getLogger("pipeline.forward")


def _series(site_data_dir: Path, sym: str) -> dict[str, float]:
    data = read_series(site_data_dir / "series" / "yahoo" / f"{sym}.json")
    if not data:
        return {}
    k = data.columns.index("adj_close") if "adj_close" in data.columns else 1
    return {r[0]: r[k] for r in data.rows if r[k] is not None}


def run(out_dir: Path, builder, site_data_dir: Path, offline: bool = False, download=None) -> dict[str, Any]:
    """``builder``: the ScreenerBuilder that just ran (rows and daily bars). ``download(tickers)`` returns
    ``{ticker: DataFrame}`` for stocks that left the universe (default: yfinance, one batch)."""
    folder = out_dir / "forward"
    path = folder / "outliers.csv"
    rows = outliers.read(path.read_text(encoding="utf-8")) if path.exists() else []
    spy = _series(site_data_dir, "SPY")
    days = sorted(spy)
    etfs = {sym: _series(site_data_dir, sym) for sym in set(SECTOR_ETF.values())}
    bars = builder.bars()
    extra: dict[str, dict[str, float]] = {}

    def closes(t: str) -> dict[str, float]:
        if t in extra:
            return extra[t]
        b = bars.get(t) or {}
        return {d: c for d, c in zip(b.get("d", []), b.get("c", []), strict=False) if c is not None}

    status: dict[str, Any] = {"status": "ok", "error": None}
    if not days:
        status.update(status="failed", error="no SPY series: the forward test needs SPY's trading days")
        return status
    missing = outliers.due_tickers(rows, days, lambda t: bool(bars.get(t)))
    if missing and not offline:
        try:
            if download is None:
                from ..screener.volatility import download_prices

                frames = download_prices(missing, 200)
            else:
                frames = download(missing)
            for t, f in frames.items():
                close = f["Close"].dropna()
                extra[t] = {i.date().isoformat(): float(v) for i, v in close.items()}
        except Exception as exc:  # those rows wait for the next run
            status["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            log.warning("forward test: download of %d stocks failed: %s", len(missing), status["error"])
    # the cohort's day: the last trading day both the screener's bars and SPY have closed (during US market hours
    # the bars already hold today's unfinished session, which SPY's published series leaves out)
    last = max((b["d"][-1] for b in bars.values() if b.get("d")), default=None)
    day = max((d for d in days if last and d <= last), default=None)
    added = outliers.add_cohort(rows, day, builder.rows, closes) if day else 0
    filled = outliers.fill(rows, days, closes, spy, etfs, SECTOR_ETF.get)
    _atomic_write_text(path, outliers.write(rows))
    data = {
        "generated_at": iso(utc_now()),
        "first_cohort": min((r["cohort"] for r in rows), default=None),
        "last_cohort": max((r["cohort"] for r in rows), default=None),
        "horizons": list(outliers.HORIZONS),
        "all": outliers.summary(rows),
        "vol_only": outliers.summary(rows, vol_only=True),
        "missing_prices": len(missing) - len(extra),
    }
    write_json(folder / "summary.json", data, indent=None)
    status.update(cohorts=data["all"]["cohorts"], rows=len(rows), added=added, filled=filled)
    log.info(
        "forward test: %d cohorts, %d rows (+%d), %d returns filled",
        status["cohorts"],
        len(rows),
        added,
        filled,
    )
    return status
