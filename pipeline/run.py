"""Run the whole pipeline: ``python -m pipeline.run``.

1. fetch every series in ``catalog.yaml`` (FRED + ALFRED vintages, Yahoo) with last-good-copy fallback;
2. validate the hand-entered CSVs in ``data/manual/``;
3. write ``site/data/series/**.json``, ``site/data/manual/*.json`` and ``site/data/health.json``.

A failing source never stops the run: it is reported on the Data health page. The exit code is non-zero
only when the pipeline itself crashes.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from . import gha, manual
from .catalog import SOURCES, CatalogEntry, load_catalog
from .config import CATALOG_FILE, MANUAL_DIR, RAW_DIR, SITE_DATA_DIR, YAHOO_MIN_INTERVAL_S
from .fetchers import fred, yahoo
from .health import SeriesResult, build_health
from .http import FetchError, HttpClient, redact
from .store import RawCache, SeriesData, iso, read_series, utc_now, write_json, write_series

log = logging.getLogger("pipeline")


class Runner:
    def __init__(
        self,
        *,
        raw_dir: Path,
        out_dir: Path,
        offline: bool = False,
        refresh: bool = False,
        vintages: bool = True,
        fred_client: fred.FredClient | None = None,
        yahoo_http: HttpClient | None = None,
        now_iso: str | None = None,
    ) -> None:
        self.cache = RawCache(raw_dir)
        self.out_dir = out_dir
        self.offline = offline
        self.refresh = refresh
        self.with_vintages = vintages
        self.fred = fred_client or fred.FredClient(os.environ.get("FRED_API_KEY"))
        self.yahoo_http = yahoo_http or HttpClient(min_interval=YAHOO_MIN_INTERVAL_S)
        self.now_iso = now_iso or iso(utc_now())

    def series_path(self, entry: CatalogEntry) -> Path:
        return self.out_dir / "series" / entry.source / f"{entry.name}.json"

    def _download(self, entry: CatalogEntry, cached: Any) -> tuple[Any, SeriesData, bool]:
        if entry.source == "fred":
            payload, reused = fred.fetch(self.fred, entry.id, None if self.refresh else cached)
            return payload, fred.normalize(payload), reused
        payload = yahoo.fetch(entry.id, self.yahoo_http)
        return payload, yahoo.normalize(payload), False

    def _normalize(self, entry: CatalogEntry, payload: Any) -> SeriesData:
        return fred.normalize(payload) if entry.source == "fred" else yahoo.normalize(payload)

    def update(self, entry: CatalogEntry, *, skip: bool = False) -> SeriesResult:
        hit = self.cache.load(entry.source, entry.name)
        cached_payload, cached_at = hit if hit else (None, None)
        data: SeriesData | None = None
        error: str | None = None
        if skip:
            status, error = "skipped", "not requested in this run"
        elif self.offline:
            status, error = "offline", "offline run (network not used)"
        else:
            try:
                payload, data, reused = self._download(entry, cached_payload)
                self.cache.save(entry.source, entry.name, payload)
                res = SeriesResult(entry, data, "unchanged" if reused else "ok", "fresh", self.now_iso)
                self._publish(entry, data, self.now_iso)
                if entry.vintages and self.with_vintages:
                    res.vintages = self._vintages(entry, payload["series"].get("last_updated"))
                return res
            except Exception as exc:  # one bad source must not stop the others
                status = "failed"
                error = redact(str(exc) if isinstance(exc, FetchError) else f"{type(exc).__name__}: {exc}")
                if not isinstance(exc, FetchError):
                    log.exception("unexpected error while updating %s", entry.key)
                log.warning("%s: fetch failed: %s", entry.key, error)

        res = SeriesResult(entry, None, status, "none", error=error)
        if cached_payload is not None:
            try:
                data = self._normalize(entry, cached_payload)
                res.data, res.data_from, res.data_fetched_at = data, "raw-cache", cached_at
                self._publish(entry, data, cached_at)
            except Exception as exc:
                log.warning("%s: cached copy unusable: %s", entry.key, exc)
        if res.data is None and (published := read_series(self.series_path(entry))):
            res.data, res.data_from = published, "published"
            res.data_fetched_at = published.meta.get("fetched_at")
        if entry.vintages and (v := self.cache.load("alfred", entry.name)):
            res.vintages = self._vintage_info(v[0], v[1], "not fetched", None)
        return res

    def _publish(self, entry: CatalogEntry, data: SeriesData, fetched_at: str | None) -> None:
        header = {
            "key": entry.key,
            "source": SOURCES[entry.source],
            "id": entry.id,
            "label": entry.label,
            "block": entry.block,
            "url": entry.source_url,
            **data.meta,
            "fetched_at": fetched_at,
        }
        write_series(self.series_path(entry), header, data)

    @staticmethod
    def _vintage_info(
        payload: dict[str, Any], saved_at: str | None, status: str, error: str | None
    ) -> dict[str, Any]:
        rows = payload.get("rows", [])
        return {
            "status": status,
            "rows": len(rows),
            "latest_vintage": max((r[1] for r in rows), default=None),
            "saved_at": saved_at,
            "error": error,
        }

    def _vintages(self, entry: CatalogEntry, last_updated: str | None) -> dict[str, Any]:
        hit = self.cache.load("alfred", entry.name)
        cached, cached_at = hit if hit else (None, None)
        try:
            payload, reused = fred.fetch_vintages(
                self.fred, entry.id, last_updated, None if self.refresh else cached
            )
            if not reused:
                self.cache.save("alfred", entry.name, payload)
            return self._vintage_info(
                payload, cached_at if reused else self.now_iso, "unchanged" if reused else "ok", None
            )
        except FetchError as exc:
            log.warning("%s: ALFRED vintages failed: %s", entry.key, exc)
            if cached:
                return self._vintage_info(cached, cached_at, "failed", str(exc))
            return {
                "status": "failed",
                "rows": 0,
                "latest_vintage": None,
                "saved_at": None,
                "error": str(exc),
            }

    def prune(self, entries: list[CatalogEntry]) -> None:
        """Remove published series that are no longer in the catalog."""
        keep = {self.series_path(e) for e in entries}
        for path in (self.out_dir / "series").glob("*/*.json"):
            if path not in keep:
                path.unlink()
                log.info("removed %s (no longer in the catalog)", path)


def _report(health: dict[str, Any]) -> None:
    s, m = health["summary"]["series"], health["summary"]["manual"]
    log.info(
        "series: %d total, %d ok, %d stale, %d failed, %d missing",
        s["total"],
        s["ok"],
        s["stale"],
        s["failed"],
        s["missing"],
    )
    log.info(
        "manual files: %d ok, %d due, %d awaiting data, %d with errors",
        m["ok"],
        m["due"],
        m["awaiting"],
        m["files_with_errors"],
    )
    lines = [
        "## Data update",
        "",
        f"Series: **{s['ok']} ok**, {s['stale']} stale, {s['failed']} failed, {s['missing']} missing "
        f"(of {s['total']}).",
        f"Manual files: {m['ok']} ok, {m['due']} due, {m['awaiting']} awaiting data, "
        f"{m['files_with_errors']} with errors.",
        "",
    ]
    problems = [x for x in health["series"] if x["status"] != "ok"]
    if problems:
        lines += ["| Series | Status | Last observation | Detail |", "|---|---|---|---|"]
    for x in problems:
        detail = x["fetch"]["error"] or f"{x['age_days']} days old (limit {x['max_age_days']})"
        lines.append(f"| {x['key']} | {x['status']} | {x['last_date'] or '-'} | {detail} |")
        level = "warning" if x["status"] in ("failed", "missing") else "notice"
        gha.annotate(level, f"{x['key']} ({x['label']}): {x['status']} - {detail}", title="Data health")
    gha.step_summary("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch all data and rebuild site/data/.")
    parser.add_argument("--offline", action="store_true", help="no network: rebuild from the raw cache")
    parser.add_argument("--only", default="fred,yahoo", help="comma list of sources to fetch (default: all)")
    parser.add_argument("--no-vintages", action="store_true", help="skip ALFRED vintages")
    parser.add_argument("--refresh", action="store_true", help="re-download even if the source is unchanged")
    parser.add_argument("--today", type=date.fromisoformat, default=None, help="pretend today is YYYY-MM-DD")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out-dir", type=Path, default=SITE_DATA_DIR)
    parser.add_argument("--manual-dir", type=Path, default=MANUAL_DIR)
    parser.add_argument("--catalog", type=Path, default=CATALOG_FILE)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    for noisy in ("yfinance", "peewee", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.CRITICAL)

    today = args.today or date.today()
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    entries = load_catalog(args.catalog)
    runner = Runner(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        offline=args.offline,
        refresh=args.refresh,
        vintages=not args.no_vintages,
    )
    if not args.offline and "fred" in only and not runner.fred.api_key:
        log.warning("FRED_API_KEY is not set: FRED series will use their last good copy")
        gha.annotate("warning", "FRED_API_KEY secret is not set; FRED data was not refreshed.", title="Setup")

    results = []
    for i, entry in enumerate(entries, 1):
        res = runner.update(entry, skip=entry.source not in only)
        log.info(
            "[%2d/%d] %-22s %-9s last=%s",
            i,
            len(entries),
            entry.key,
            res.fetch_status,
            res.data.last_date if res.data else "-",
        )
        results.append(res)
    runner.prune(entries)

    manual_entries = []
    for ds in manual.load_all(today, args.manual_dir):
        write_json(
            args.out_dir / "manual" / f"{ds.spec.name}.json", manual.to_site_json(ds, today), indent=None
        )
        manual_entries.append(manual.health_entry(ds, today))

    health = build_health(results, manual_entries, generated_at=runner.now_iso, today=today)
    write_json(args.out_dir / "health.json", health, indent=None)
    _report(health)
    log.info(
        "wrote %s (HTTP requests: FRED %d, Yahoo fallback %d)",
        args.out_dir / "health.json",
        runner.fred.http.requests_made,
        runner.yahoo_http.requests_made,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
