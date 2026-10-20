"""On-disk storage: atomic JSON writes, the raw cache, and the published per-series files.

"Last good copy" works in three tiers:
1. a fresh fetch, validated, replaces the raw cache entry in ``data/raw/``;
2. if the fetch fails, the raw cache entry (from an earlier run) is used instead;
3. if there is no raw cache either (e.g. a fresh CI runner), the previously published
   ``site/data/series/*.json`` file, which the workflow commits, is kept unchanged.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.chmod(tmp, 0o644)  # mkstemp creates 0600 files; the website needs them world-readable
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_json(path: Path, obj: Any, *, indent: int | None = 1) -> None:
    text = json.dumps(obj, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))
    _atomic_write_text(path, text + "\n")


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@dataclass
class SeriesData:
    """A normalized time series: ``rows`` are ``[date, value, ...]`` sorted by date (ISO strings)."""

    meta: dict[str, Any]
    columns: list[str]
    rows: list[list[Any]] = field(default_factory=list)

    @property
    def last_date(self) -> str | None:
        return self.rows[-1][0] if self.rows else None

    @property
    def last_value(self) -> Any:
        return self.rows[-1][1] if self.rows else None


def write_series(path: Path, header: dict[str, Any], data: SeriesData) -> None:
    """Write one observation per line so daily commits produce small, readable git diffs."""
    head = dict(header)
    head["columns"] = data.columns
    body = json.dumps(head, ensure_ascii=False, separators=(",", ":"))[:-1]
    rows = ",\n".join(json.dumps(r, separators=(",", ":")) for r in data.rows)
    _atomic_write_text(path, f'{body},"observations":[\n{rows}\n]}}\n')


def read_series(path: Path) -> SeriesData | None:
    obj = read_json(path)
    if not isinstance(obj, dict) or "observations" not in obj:
        return None
    rows = obj.pop("observations")
    columns = obj.pop("columns", ["date", "value"])
    return SeriesData(meta=obj, columns=columns, rows=rows)


class RawCache:
    """Raw responses per source, kept between runs (``actions/cache`` on GitHub Actions)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, source: str, name: str) -> Path:
        return self.root / source / f"{name}.json"

    def save(self, source: str, name: str, payload: Any, saved_at: datetime | None = None) -> None:
        write_json(
            self.path(source, name), {"saved_at": iso(saved_at or utc_now()), "payload": payload}, indent=None
        )

    def load(self, source: str, name: str) -> tuple[Any, str] | None:
        obj = read_json(self.path(source, name))
        if not isinstance(obj, dict) or "payload" not in obj:
            return None
        return obj["payload"], obj.get("saved_at", "")
