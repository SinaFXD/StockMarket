"""Build the Sector Screener data: ``site/data/screener/stocks.json``.

1. Universe: Yahoo's equity screener, one query per sector, every US-listed stock above the market-cap filter.
2. Estimates: one ``quoteSummary`` per stock, refreshed when older than ``summary_max_age_hours``, at most
   ``summary_budget`` per run, oldest first; a run stops downloading after ``summary_fail_stop`` failures in a
   row (Yahoo throttling) and keeps the previous copies.
3. The 11 numbers, the data checks and the sector averages (``numbers.py``).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..config import SCREENER
from ..http import redact
from ..store import RawCache, iso, read_series, utc_now, write_json
from . import numbers, outliers, volatility, yahoo

log = logging.getLogger("pipeline.screener")
COLUMNS = [
    "t",
    "name",
    "sector",
    "industry",
    "price",
    "mcap",
    "eps0",
    "eps1",
    "eps2",
    "eg1",
    "eg2",
    "pe1",
    "pe2",
    "peg1",
    "peg2",
    "fy",
    "analysts",
    "rg1",
    "rg2",
    "eps1_rev90",
    "earnings",
    "flags",
    "cls",
    "why",
    "notes",
    "eg1_pct",
    "eg2_pct",
    "pe_prem",
    "rv",
    "atr",
    "iv",
    "vol_ok",
]
CANDIDATES = ("positive", "negative", "post_growth", "turnaround", "value_trap")


def _round(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 4) if abs(v) < 1000 else round(v)
    return v


class ScreenerBuilder:
    def __init__(
        self,
        cache: RawCache,
        *,
        offline: bool = False,
        params: dict | None = None,
        screen=None,
        get_json=None,
        download=None,
        option_ticker=None,
        vix: float | None = None,
        rate: float = 0.04,
        now: datetime | None = None,
    ) -> None:
        self.cache, self.offline = cache, offline
        self.p = {**SCREENER, **(params or {})}
        self._screen, self._get_json = screen, get_json
        self._download, self._option_ticker = download, option_ticker  # test doubles
        self.vix, self.rate = vix, rate
        self.now = now or utc_now()
        self.status: dict[str, Any] = {}

    # -- universe ----------------------------------------------------------------------------------------
    def universe(self) -> list[dict[str, Any]]:
        error = None
        if not self.offline:
            try:
                screen = self._screen or yahoo.default_screen()
                try:
                    quotes = yahoo.fetch_universe(self.p["min_market_cap"], screen)
                except (
                    Exception
                ) as first:  # Yahoo sometimes refuses the first call (401) until its cookie is fresh
                    log.info("screener universe: retrying after %s", first)
                    time.sleep(2 if not self._screen else 0)
                    quotes = yahoo.fetch_universe(self.p["min_market_cap"], screen)
                self.cache.save("screener", "universe", {"quotes": quotes}, self.now)
                self.status["universe"] = {"status": "ok", "stocks": len(quotes), "saved_at": iso(self.now)}
                return quotes
            except Exception as exc:  # keep the last good copy
                error = redact(f"{type(exc).__name__}: {exc}")
                log.warning("screener universe: %s", error)
        hit = self.cache.load("screener", "universe")
        quotes = hit[0]["quotes"] if hit else []
        self.status["universe"] = {
            "status": ("cached" if not error else "failed") if hit else "missing",
            "stocks": len(quotes),
            "saved_at": hit[1] if hit else None,
            "error": error,
        }
        return quotes

    # -- estimates ---------------------------------------------------------------------------------------
    def summaries(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        hit = self.cache.load("screener", "summaries")
        store: dict[str, dict[str, Any]] = dict(hit[0]) if hit else {}
        fetched = failed = 0
        last_error = None
        if not self.offline and symbols:
            get_json = self._get_json or yahoo.default_get_json()
            limit = self.now - timedelta(hours=self.p["summary_max_age_hours"])

            def age_key(sym: str) -> str:
                return (store.get(sym) or {}).get("fetched_at") or ""

            due = [s for s in sorted(symbols, key=age_key) if age_key(s) < iso(limit)]
            streak = 0
            for sym in due[: int(self.p["summary_budget"])]:
                try:
                    store[sym] = {"fetched_at": iso(self.now), "data": yahoo.fetch_summary(sym, get_json)}
                    fetched += 1
                    streak = 0
                except Exception as exc:
                    failed += 1
                    streak += 1
                    last_error = redact(f"{sym}: {type(exc).__name__}: {exc}")[:300]
                    if streak >= self.p["summary_fail_stop"]:
                        log.warning("screener: %d failures in a row, keeping cached estimates", streak)
                        break
            self.cache.save("screener", "summaries", store, self.now)
        have = sum(1 for s in symbols if s in store)
        self.status["estimates"] = {
            "status": "ok" if not failed else "partial",
            "downloaded": fetched,
            "failed": failed,
            "with_estimates": have,
            "error": last_error,
        }
        return store

    # -- volatility ------------------------------------------------------------------------------------------
    def realised(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        hit = self.cache.load("screener", "realised")
        store: dict[str, dict[str, Any]] = dict(hit[0]) if hit else {}
        error = None
        if not self.offline and symbols:
            try:
                frames = volatility.download_prices(symbols, int(self.p["price_chunk"]), self._download)
                for sym, frame in frames.items():
                    store[sym] = {
                        **volatility.realised(frame, int(self.p["rv_days"]), int(self.p["atr_days"])),
                        "date": frame.index[-1].date().isoformat(),
                    }
                self.cache.save("screener", "realised", store, self.now)
            except Exception as exc:  # keep yesterday's numbers
                error = redact(f"{type(exc).__name__}: {exc}")[:300]
                log.warning("screener prices: %s", error)
        self.status["prices"] = {
            "status": "ok" if not error else "failed",
            "with_volatility": sum(1 for s in symbols if (store.get(s) or {}).get("rv") is not None),
            "error": error,
        }
        return store

    def implied(self, rows: list[dict[str, Any]], today: date) -> dict[str, dict[str, Any]]:
        hit = self.cache.load("screener", "implied")
        store: dict[str, dict[str, Any]] = dict(hit[0]) if hit else {}
        fetched = failed = 0
        last_error = None
        if not self.offline:
            limit = iso(self.now - timedelta(hours=self.p["summary_max_age_hours"]))
            due = [
                r
                for r in sorted(rows, key=lambda r: -(r["mcap"] or 0))
                if r["cls"] in CANDIDATES
                and r["price"]
                and (store.get(r["t"]) or {}).get("fetched_at", "") < limit
            ]
            streak = 0
            for i, r in enumerate(due[: int(self.p["iv_budget"])]):
                if i and self.p["iv_pause_s"] and not self._option_ticker:
                    time.sleep(self.p["iv_pause_s"])
                try:
                    ticker = self._option_ticker(r["t"]) if self._option_ticker else None
                    res = volatility.fetch_iv(
                        r["t"], r["price"], today, int(self.p["iv_target_days"]), self.rate, ticker
                    )
                    store[r["t"]] = {**res, "fetched_at": iso(self.now)}
                    fetched += 1
                    streak = 0
                except Exception as exc:
                    failed += 1
                    streak += 1
                    last_error = redact(f"{r['t']}: {type(exc).__name__}: {exc}")[:300]
                    if streak >= self.p["summary_fail_stop"]:
                        break
            self.cache.save("screener", "implied", store, self.now)
        self.status["options"] = {
            "status": "ok" if not failed else "partial",
            "downloaded": fetched,
            "failed": failed,
            "error": last_error,
        }
        return store

    def attach_volatility(self, rows: list[dict[str, Any]], today: date) -> None:
        real = self.realised([r["t"] for r in rows])
        imp = self.implied(rows, today)
        need = self.p["vol_vs_vix"]
        for r in rows:
            rv = (real.get(r["t"]) or {}).get("rv")
            atr = (real.get(r["t"]) or {}).get("atr")
            iv = (imp.get(r["t"]) or {}).get("iv")
            r["rv"], r["atr"], r["iv"] = rv, atr, iv
            ratios = [x / self.vix for x in (rv, iv) if x is not None and self.vix]
            r["vol_ok"] = None if not ratios else all(x >= need for x in ratios)

    # -- build -------------------------------------------------------------------------------------------
    def build(self, today: date) -> dict[str, Any]:
        quotes = self.universe()
        store = self.summaries([q["symbol"] for q in quotes if q.get("symbol")])
        rows = []
        for q in quotes:
            item = store.get(q.get("symbol")) or {}
            rows.append(numbers.compute(q, item.get("data"), item.get("fetched_at"), today, self.p))
        numbers.mark_duplicates(rows)
        medians = outliers.classify(rows, self.p)
        self.attach_volatility(rows, today)
        stats = numbers.sector_stats(rows)
        counts = {code: sum(1 for r in rows if code in r["flags"]) for code in numbers.CHECKS}
        return {
            "generated_at": iso(self.now),
            "as_of": today.isoformat(),
            "params": self.p,
            "columns": COLUMNS,
            "rows": [[_round(r.get(c)) for c in COLUMNS] for r in rows],
            "duplicates": {r["t"]: r["duplicate_of"] for r in rows if r.get("duplicate_of")},
            "sectors": stats,
            "checks": {
                k: {"label": v[0], "text": v[1], "excluded": v[2], "count": counts[k]}
                for k, v in numbers.CHECKS.items()
            },
            "status": self.status,
            "vix": self.vix,
            "medians": medians,
            "categories": {
                k: {"label": v[0], "side": v[1], "text": v[2], "count": sum(1 for r in rows if r["cls"] == k)}
                for k, v in outliers.CATEGORIES.items()
            },
        }


def market_inputs(site_data_dir: Path) -> dict[str, float | None]:
    """VIX (the volatility filter's yardstick) and the 3-month T-bill rate (for implied volatility), from the
    series the pipeline has just published."""

    def last(path: Path) -> float | None:
        data = read_series(path)
        vals = [r[1] for r in (data.rows if data else []) if r[1] is not None]
        return float(vals[-1]) if vals else None

    vix = last(site_data_dir / "series" / "yahoo" / "VIX.json") or last(
        site_data_dir / "series" / "fred" / "VIXCLS.json"
    )
    rate = last(site_data_dir / "series" / "fred" / "DGS3MO.json")
    return {"vix": vix, "rate": rate / 100 if rate is not None else 0.04}


def write(out_dir: Path, data: dict[str, Any]) -> None:
    write_json(out_dir / "screener" / "stocks.json", data, indent=None)


def status_of(data: dict[str, Any]) -> dict[str, Any]:
    st = data["status"]
    uni, est = st.get("universe", {}), st.get("estimates", {})
    ok = (
        uni.get("status") in ("ok", "cached")
        and est.get("status") == "ok"
        and st.get("prices", {}).get("status", "ok") == "ok"
    )
    return {
        "status": "ok" if ok else "degraded" if data["rows"] else "failed",
        "stocks": len(data["rows"]),
        "in_averages": data["sectors"]["all"]["n_used"],
        "universe": uni,
        "estimates": est,
        "prices": st.get("prices"),
        "options": st.get("options"),
    }


__all__ = ["ScreenerBuilder", "write", "status_of", "UTC"]
