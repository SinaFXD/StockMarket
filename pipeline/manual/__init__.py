"""Hand-entered monthly data (ISM, NFIB, China PMIs): schemas, validation and release calendars."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from ..config import MANUAL_DIR
from .loader import Issue, ManualDataset, freshness, load
from .schemas import MANUAL_FILES, ManualFile

__all__ = [
    "Issue",
    "ManualDataset",
    "ManualFile",
    "MANUAL_FILES",
    "freshness",
    "load",
    "load_all",
    "to_site_json",
    "health_entry",
]


def load_all(today: date, manual_dir: Path = MANUAL_DIR) -> list[ManualDataset]:
    return [load(spec, manual_dir / spec.filename, today) for spec in MANUAL_FILES]


def to_site_json(ds: ManualDataset, today: date) -> dict[str, Any]:
    """The validated rows the website and the signal modules read (``site/data/manual/<name>.json``)."""
    cols = ds.spec.column_names
    return {
        "name": ds.spec.name,
        "title": ds.spec.title,
        "source": ds.spec.source,
        "columns": cols,
        "labels": {c.name: c.label for c in ds.spec.columns},
        "freshness": freshness(ds, today),
        "rows": [[r[c] for c in cols] for r in ds.rows],
    }


def health_entry(ds: ManualDataset, today: date) -> dict[str, Any]:
    fresh = freshness(ds, today)
    return {
        "name": ds.spec.name,
        "file": f"data/manual/{ds.spec.filename}",
        "title": ds.spec.title,
        "source": ds.spec.source,
        "optional": ds.spec.optional,
        **fresh,
        "errors": [e.as_dict() for e in ds.errors],
        "warnings": [w.as_dict() for w in ds.warnings],
    }
