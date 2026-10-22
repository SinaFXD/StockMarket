"""Run the whole pipeline: ``python -m pipeline.run``.

1. fetch every series in ``catalog.yaml`` (FRED + ALFRED vintages, Yahoo, UMich, Eurostat, OECD) with last-good-copy
   fallback;
2. validate the hand-entered CSVs in ``data/manual/``;
3. build the release calendar (``site/data/calendar.json``) and the Sector Screener
   (``site/data/screener/stocks.json``);
4. compute the Macro Desk (signals, bias, monthly point-in-time history, daily log) into ``site/data/macro/``;
5. write ``site/data/series/**.json``, ``site/data/manual/*.json`` and ``site/data/health.json``.

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
from .calendar import CalendarBuilder
from .calendar import status_of as calendar_status
from .catalog import SOURCES, CatalogEntry, load_catalog
from .config import CATALOG_FILE, IDEAS_DIR, MANUAL_DIR, RAW_DIR, SITE_DATA_DIR, YAHOO_MIN_INTERVAL_S
from .fetchers import eurostat, fred, oecd, umich, yahoo
from .forward.build import run as run_forward
from .health import SeriesResult, build_health
from .http import FetchError, HttpClient, redact
from .screener.build import ScreenerBuilder, market_inputs
from .screener.build import status_of as screener_status
from .screener.build import write as write_screener
from .signals.build import build as build_macro
from .signals.data import Library
from .store import RawCache, SeriesData, iso, read_series, utc_now, write_json, write_series
from .themes.build import build as build_themes
from .themes.build import status_of as themes_status
from .workbench.build import build_ideas, ideas_status, write_ideas, write_stock_pages

log = logging.getLogger("pipeline")
OTHER_SOURCES = {"umich": umich, "eurostat": eurostat, "oecd": oecd}


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
        self.other_http = HttpClient(min_interval=0.5)
        self.now_iso = now_iso or iso(utc_now())

    def series_path(self, entry: CatalogEntry) -> Path:
        return self.out_dir / "series" / entry.source / f"{entry.name}.json"

    def _download(self, entry: CatalogEntry, cached: Any) -> tuple[Any, SeriesData, bool]:
        if entry.source == "fred":
            payload, reused = fred.fetch(self.fred, entry.id, None if self.refresh else cached)
            return payload, fred.normalize(payload), reused
        if entry.source == "yahoo":
            payload = yahoo.fetch(entry.id, self.yahoo_http)
        else:
            payload = OTHER_SOURCES[entry.source].fetch(entry.id, self.other_http)
        return payload, self._normalize(entry, payload), False

    def _normalize(self, entry: CatalogEntry, payload: Any) -> SeriesData:
        if entry.source == "fred":
            return fred.normalize(payload)
        if entry.source == "yahoo":
            return yahoo.normalize(payload)
        return OTHER_SOURCES[entry.source].normalize(payload)

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
        except Exception as exc:  # vintages are extra: never let them fail the series itself
            error = redact(str(exc) if isinstance(exc, FetchError) else f"{type(exc).__name__}: {exc}")
            log.warning("%s: ALFRED vintages failed: %s", entry.key, error)
            if cached:
                return self._vintage_info(cached, cached_at, "failed", error)
            return {"status": "failed", "rows": 0, "latest_vintage": None, "saved_at": None, "error": error}

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
    grouped: dict[tuple[str, str], list[str]] = {}
    for x in problems:
        detail = x["fetch"]["error"] or f"{x['age_days']} days old (limit {x['max_age_days']})"
        lines.append(f"| {x['key']} | {x['status']} | {x['last_date'] or '-'} | {detail} |")
        level = "warning" if x["status"] in ("failed", "missing") else "notice"
        grouped.setdefault((level, f"{x['status']} - {detail}"), []).append(x["key"])
    for (level, what), keys in grouped.items():  # one annotation per distinct problem (GitHub shows only 10)
        names = ", ".join(keys[:5]) + (f" and {len(keys) - 5} more" if len(keys) > 5 else "")
        gha.annotate(level, f"{len(keys)} series {what}: {names}", title="Data health")
    gha.step_summary("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch all data and rebuild site/data/.")
    parser.add_argument("--offline", action="store_true", help="no network: rebuild from the raw cache")
    parser.add_argument(
        "--only",
        default=",".join([*SOURCES, "calendar", "screener"]),
        help="comma list of sources to fetch (default: all, plus the release calendar and the screener)",
    )
    parser.add_argument("--no-vintages", action="store_true", help="skip ALFRED vintages")
    parser.add_argument(
        "--screener-budget", type=int, default=None, help="max screener estimate downloads (default: config)"
    )
    parser.add_argument("--refresh", action="store_true", help="re-download even if the source is unchanged")
    parser.add_argument("--today", type=date.fromisoformat, default=None, help="pretend today is YYYY-MM-DD")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out-dir", type=Path, default=SITE_DATA_DIR)
    parser.add_argument("--manual-dir", type=Path, default=MANUAL_DIR)
    parser.add_argument("--ideas-dir", type=Path, default=IDEAS_DIR)
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

    calendar: dict[str, Any]
    try:  # the calendar is context: a broken page must not stop the data update
        cal = CalendarBuilder(
            runner.cache, runner.other_http, runner.fred, offline=args.offline or "calendar" not in only
        ).build(today)
        write_json(args.out_dir / "calendar.json", cal, indent=None)
        calendar = calendar_status(cal)
        log.info(
            "calendar: %d events, sources %s",
            calendar["events"],
            {s["id"]: s["status"] for s in cal["sources"]},
        )
    except Exception as exc:
        log.exception("calendar build failed")
        calendar = {"status": "failed", "error": redact(f"{type(exc).__name__}: {exc}"), "sources": []}

    screener: dict[str, Any]
    builder = None
    try:  # the screener is a separate module: a failure must not stop the data update
        budget = (
            {"summary_budget": args.screener_budget, "iv_budget": args.screener_budget}
            if args.screener_budget is not None
            else None
        )
        builder = ScreenerBuilder(
            runner.cache,
            offline=args.offline or "screener" not in only,
            params=budget,
            **market_inputs(args.out_dir),
        )
        data = builder.build(today)
        write_screener(args.out_dir, data)
        screener = screener_status(data)
        screener["workbench"] = write_stock_pages(args.out_dir, builder, args.out_dir, data["as_of"])
        log.info("screener: %d stocks, %d in sector averages", screener["stocks"], screener["in_averages"])
    except Exception as exc:
        log.exception("screener build failed")
        screener = {"status": "failed", "error": redact(f"{type(exc).__name__}: {exc}")}

    forward: dict[str, Any] = {"status": "skipped", "error": None}
    if builder is not None and builder.rows:
        try:  # the live record of the screener's types; a failure keeps yesterday's record
            forward = run_forward(
                args.out_dir, builder, args.out_dir, offline=args.offline or "screener" not in only
            )
            forward["error"] = redact(forward["error"]) if forward.get("error") else None
        except Exception as exc:
            log.exception("forward test failed")
            forward = {"status": "failed", "error": redact(f"{type(exc).__name__}: {exc}")}

    macro: dict[str, Any] = {"status": "ok", "error": None}
    try:  # a bug in the Macro Desk must not stop the data update
        latest = build_macro(
            args.out_dir,
            today,
            Library.load(
                today,
                site_data_dir=args.out_dir,
                raw_dir=args.raw_dir,
                manual_dir=args.manual_dir,
                catalog=entries,
            ),
        )
        macro.update(
            bias=latest["bias"]["score"],
            state=latest["bias"]["state"],
            used=latest["bias"]["used"],
            total=latest["bias"]["total"],
        )
    except Exception as exc:
        log.exception("Macro Desk build failed")
        macro = {"status": "failed", "error": redact(f"{type(exc).__name__}: {exc}")}
        gha.annotate("error", f"Macro Desk not updated: {macro['error']}", title="Macro Desk")

    ideas: dict[str, Any]
    try:  # saved trade ideas (data/ideas/*.md): problems are reported, never stop the update
        idea_data = build_ideas(args.ideas_dir)
        write_ideas(args.out_dir, idea_data)
        ideas = ideas_status(idea_data)
        for p in idea_data["problems"]:
            for e in p["errors"]:
                gha.annotate("error", f"{p['file']}: {e}", title="Trade ideas")
    except Exception as exc:
        log.exception("ideas build failed")
        ideas = {"status": "failed", "error": redact(f"{type(exc).__name__}: {exc}")}

    themes: dict[str, Any]
    try:  # macro-driven ideas: context built from the files above, never stops the update
        theme_data = build_themes(args.out_dir)
        write_json(args.out_dir / "themes.json", theme_data, indent=None)
        themes = themes_status(theme_data)
    except Exception as exc:
        log.exception("themes build failed")
        themes = {"status": "failed", "error": redact(f"{type(exc).__name__}: {exc}")}

    health = build_health(results, manual_entries, generated_at=runner.now_iso, today=today)
    health["macro"] = macro
    health["calendar"] = calendar
    health["screener"] = screener
    health["ideas"] = ideas
    health["themes"] = themes
    health["forward"] = forward
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
