"""Build the Trade Idea Workbench data.

- ``site/data/stocks/<T>.json``: one trade-idea page per screener stock (``stock.py``), rebuilt every run from the
  screener's caches. These files are published with the website but **not committed** (one per stock, ~2,000
  files that change every day); the raw cache keeps their last good inputs.
- ``site/data/ideas.json``: the ideas saved in ``data/ideas/*.md`` (``ideas.py``) and the problems found in them.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..config import WORKBENCH
from ..store import iso, read_series, utc_now, write_json
from . import ideas, stock, targets

log = logging.getLogger("pipeline.workbench")
STOCKS_DIR = "stocks"


def etf_returns(site_data_dir: Path) -> dict[str, float | None]:
    """3-month (63 trading days) return of SPY and the SPDR sector ETFs, for relative strength."""
    out: dict[str, float | None] = {}
    for sym in ["SPY", *stock.SECTOR_ETF.values()]:
        data = read_series(site_data_dir / "series" / "yahoo" / f"{sym}.json")
        closes = [r[1] for r in (data.rows if data else [])[-200:]]
        out[sym] = targets.period_return(closes, 63)
    return out


def safe_name(ticker: str) -> str:
    """File name of a ticker's page (tickers are letters, digits, dots and dashes)."""
    return "".join(c for c in ticker.upper() if c.isalnum() or c in ".-")


def write_stock_pages(out_dir: Path, builder, site_data_dir: Path, as_of: str) -> dict[str, Any]:
    """One file per stock in the screener; files of stocks that left the universe are removed."""
    folder = out_dir / STOCKS_DIR
    etfs = etf_returns(site_data_dir)
    bars = builder.bars()
    quotes = {q.get("symbol"): q for q in builder.quotes}
    p = {**WORKBENCH}
    written: set[str] = set()
    for row in builder.rows:
        t = row["t"]
        name = safe_name(t or "")
        if not name:
            continue
        item = builder.summary_store.get(t) or {}
        page = stock.build(
            row,
            quotes.get(t) or {},
            item.get("data"),
            bars.get(t),
            builder.accounts.get(t),
            etfs,
            p,
            as_of,
        )
        write_json(folder / f"{name}.json", page, indent=None)
        written.add(f"{name}.json")
    removed = 0
    if folder.is_dir():
        for path in folder.glob("*.json"):
            if path.name not in written:
                path.unlink()
                removed += 1
    with_prices = sum(1 for r in builder.rows if bars.get(r["t"]))
    log.info("workbench: %d stock pages (%d with prices), %d removed", len(written), with_prices, removed)
    return {"pages": len(written), "with_prices": with_prices}


def build_ideas(ideas_dir: Path) -> dict[str, Any]:
    data = ideas.load(ideas_dir)
    return {"generated_at": iso(utc_now()), "params": WORKBENCH, **data}


def write_ideas(out_dir: Path, data: dict[str, Any]) -> None:
    write_json(out_dir / "ideas.json", data, indent=None)


def ideas_status(data: dict[str, Any]) -> dict[str, Any]:
    errors = sum(len(p["errors"]) for p in data["problems"])
    return {
        "status": "failed" if errors else "ok",
        "ideas": len(data["ideas"]),
        "errors": errors,
        "warnings": sum(len(p["warnings"]) for p in data["problems"]),
    }
