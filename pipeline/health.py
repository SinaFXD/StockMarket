"""The data-health report (``site/data/health.json``) shown on the website's "Data health" page."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from . import __version__
from .catalog import BLOCKS, SOURCES, CatalogEntry
from .config import MAX_AGE_DAYS
from .store import SeriesData

SPARK_POINTS = 60
SPARK_DAYS = 730


@dataclass
class SeriesResult:
    entry: CatalogEntry
    data: SeriesData | None
    fetch_status: str  # ok | unchanged | failed | offline | skipped
    data_from: str  # fresh | raw-cache | published | none
    data_fetched_at: str | None = None
    error: str | None = None
    vintages: dict[str, Any] | None = None


def max_age_days(entry: CatalogEntry, frequency: str | None) -> int:
    if entry.max_age_days:
        return int(entry.max_age_days)
    return MAX_AGE_DAYS.get(frequency or "", MAX_AGE_DAYS["monthly"])


def spark(data: SeriesData) -> list[list[Any]]:
    """Up to ``SPARK_POINTS`` evenly spaced ``[date, value]`` points from the last two years (trend line)."""
    if not data.rows:
        return []
    cutoff = (date.fromisoformat(data.rows[-1][0]) - timedelta(days=SPARK_DAYS)).isoformat()
    recent = [[r[0], r[1]] for r in data.rows if r[0] >= cutoff and r[1] is not None]
    if len(recent) <= SPARK_POINTS:
        return recent
    step = (len(recent) - 1) / (SPARK_POINTS - 1)
    return [recent[round(i * step)] for i in range(SPARK_POINTS)]


def series_entry(res: SeriesResult, today: date) -> dict[str, Any]:
    e, data = res.entry, res.data
    meta = data.meta if data else {}
    frequency = meta.get("frequency")
    limit = max_age_days(e, frequency)
    age = max(0, (today - date.fromisoformat(data.last_date)).days) if data and data.last_date else None
    if data is None or not data.rows:
        status = "missing"
    elif res.fetch_status == "failed":
        status = "failed"
    elif age is not None and age > limit:
        status = "stale"
    else:
        status = "ok"
    return {
        "key": e.key,
        "source": SOURCES[e.source],
        "id": e.id,
        "label": e.label,
        "block": e.block,
        "url": e.source_url,
        "title": meta.get("title"),
        "units": meta.get("units_short") or meta.get("units"),
        "frequency": frequency,
        "first_date": data.rows[0][0] if data and data.rows else None,
        "last_date": data.last_date if data else None,
        "last_value": data.last_value if data else None,
        "observations": len(data.rows) if data else 0,
        "age_days": age,
        "max_age_days": limit,
        "status": status,
        "fetch": {
            "status": res.fetch_status,
            "error": res.error,
            "data_from": res.data_from,
            "data_fetched_at": res.data_fetched_at,
            "source_updated": meta.get("source_updated"),
            "via": meta.get("via"),
        },
        "vintages": res.vintages,
        "spark": spark(data) if data else [],
    }


def run_info() -> dict[str, Any]:
    env = os.environ
    run_url = None
    if env.get("GITHUB_RUN_ID") and env.get("GITHUB_REPOSITORY"):
        server = env.get("GITHUB_SERVER_URL", "https://github.com")
        run_url = f"{server}/{env['GITHUB_REPOSITORY']}/actions/runs/{env['GITHUB_RUN_ID']}"
    return {
        "pipeline_version": __version__,
        "git_sha": env.get("GITHUB_SHA"),
        "run_url": run_url,
        "trigger": env.get("GITHUB_EVENT_NAME", "local"),
    }


def build_health(
    results: list[SeriesResult], manual: list[dict[str, Any]], *, generated_at: str, today: date
) -> dict[str, Any]:
    series = [series_entry(r, today) for r in results]
    s_counts = {k: sum(1 for s in series if s["status"] == k) for k in ("ok", "stale", "failed", "missing")}
    m_counts = {k: sum(1 for m in manual if m["status"] == k) for k in ("ok", "due", "awaiting", "empty")}
    m_counts["files_with_errors"] = sum(1 for m in manual if m["errors"])
    m_counts["errors"] = sum(len(m["errors"]) for m in manual)
    return {
        "generated_at": generated_at,
        "today": today.isoformat(),
        **run_info(),
        "summary": {
            "series": {"total": len(series), **s_counts},
            "manual": {"files": len(manual), **m_counts},
        },
        "blocks": BLOCKS,
        "series": series,
        "manual": manual,
    }
