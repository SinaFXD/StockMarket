"""Compute the Macro Desk: today's signals and bias, monthly point-in-time history, and the daily log.

Writes ``site/data/macro/``:
- ``latest.json``     today's snapshot, what changed in the last month, each signal's monthly score history;
- ``history.json``    compact monthly scores since ``SIGNAL_HISTORY_START`` (charts, evidence);
- ``snapshots/<year>.json``  full month-end snapshots (the "as of" view on the website);
- ``indicators/<id>.json``  chart panels and the reading guide for each indicator page;
- ``global.json``     money markets by country and regional equity dispersion (the Global page);
- ``confirmers.json`` coincident and lagging data next to the bias (shown, not scored);
- ``evidence.json``   forward index returns after each month-end bias reading (the Evidence page);
- ``log.csv``         one row per day the pipeline ran: the live record of what the system said.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import SIGNAL_HISTORY_START, SIGNALS
from ..store import write_json
from . import international, money_markets, prices, surveys
from .base import Signal, value_at
from .bias import PRICE_ALERT_PREFIX, PRICE_ALERTS, alerts, combine, price_alert, what_changed
from .charts import build_charts
from .confirmers import build_confirmers
from .data import Library, View, month_ends
from .evidence import build_evidence, month_end
from .global_view import build_global

log = logging.getLogger("pipeline.signals")

RULES = [*money_markets.SIGNALS, *surveys.SIGNALS, *prices.SIGNALS, *international.SIGNALS]
BLOCK_OF_MODULE = {m.__name__: m.BLOCK for m in (money_markets, surveys, prices, international)}


def evaluate(rule, view: View, params: dict) -> Signal:
    try:
        sig = rule(view, params)
    except Exception as exc:  # a bug in one rule must not hide the others
        log.exception("signal %s failed for %s", rule.__name__, view.as_of)
        sig = Signal(rule.__name__, rule.__name__, BLOCK_OF_MODULE[rule.__module__], "", [])
        sig.awaiting(f"internal error ({type(exc).__name__})")
    if view.revised & set(sig.sources):
        sig.revised = True
    return sig


def snapshot(view: View, params: dict) -> dict[str, Any]:
    signals = [evaluate(rule, view, params).to_json() for rule in RULES]
    bias = combine(signals, params["bias_threshold"])
    used_revised = {src for s in signals if s["revised"] for src in s["sources"]} & view.revised
    return {
        "as_of": view.as_of.isoformat(),
        "bias": bias,
        "signals": signals,
        "alerts": alerts(signals, bias, params["bias_threshold"]),
        "price_alert": price_alert(
            bias["state"], next((s["score"] for s in signals if s["id"] == "sp500"), None)
        ),
        "revised_inputs": sorted(used_revised),
    }


def _compact(snaps: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [s["id"] for s in snaps[0]["signals"]] if snaps else []
    return {
        "months": [s["as_of"][:7] for s in snaps],
        "bias": [s["bias"]["score"] for s in snaps],
        "state": [s["bias"]["state"] for s in snaps],
        "used": [s["bias"]["used"] for s in snaps],
        "revised": [bool(s["revised_inputs"]) for s in snaps],
        "price_alert": [s.get("price_alert") for s in snaps],
        "blocks": {
            k: [s["bias"]["blocks"][k]["score"] for s in snaps]
            for k in (snaps[0]["bias"]["blocks"] if snaps else {})
        },
        "signals": {i: [next(x["score"] for x in s["signals"] if x["id"] == i) for s in snaps] for i in ids},
    }


def month_closes(prices: pd.Series, months: list[str]) -> list[float | None]:
    """The last close on or before each month-end (the S&P 500 drawn under the bias history)."""
    out = []
    for m in months:
        v = None if prices.empty else value_at(prices, month_end(m))
        out.append(None if v is None else round(v, 2))
    return out


def update_log(path: Path, latest: dict[str, Any]) -> None:
    row = {
        "date": latest["as_of"],
        "bias_score": latest["bias"]["score"],
        "bias_state": latest["bias"]["state"],
    }
    row.update({f"block_{k}": b["score"] for k, b in latest["bias"]["blocks"].items()})
    row.update({s["id"]: s["score"] for s in latest["signals"]})
    rows: dict[str, dict] = {}
    if path.exists():
        for r in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))):
            rows[r["date"]] = r
    rows[row["date"]] = row
    fields = list(row)
    for r in rows.values():
        fields += [k for k in r if k not in fields]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for d in sorted(rows):
        writer.writerow({k: ("" if v is None else v) for k, v in rows[d].items()})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(buf.getvalue(), encoding="utf-8")


def build(
    out_dir: Path, today: date, lib: Library | None = None, start: str = SIGNAL_HISTORY_START
) -> dict[str, Any]:
    lib = lib or Library.load(today)
    params = dict(SIGNALS)
    latest = snapshot(lib.view(today), params)
    before_day = today - timedelta(days=30)
    latest["what_changed"] = what_changed(latest, snapshot(lib.view(before_day), params))
    latest["compared_with"] = before_day.isoformat()

    snaps = [snapshot(lib.view(d), params) for d in month_ends(start, today)]
    compact = _compact(snaps)
    for s in latest["signals"]:
        s["history"] = [
            [m, sc] for m, sc in zip(compact["months"], compact["signals"].get(s["id"], []), strict=False)
        ]
    latest["params"] = params
    latest["price_alerts"] = {
        "prefix": PRICE_ALERT_PREFIX,
        "texts": PRICE_ALERTS,
    }  # macro.js redoes the check
    latest["blocks"] = {k: b["label"] for k, b in latest["bias"]["blocks"].items()}

    macro = out_dir / "macro"
    write_json(macro / "latest.json", latest, indent=None)
    build_charts(lib.view(today), params, macro / "indicators", [s["id"] for s in latest["signals"]])
    for name, make in (  # context pages: a bug there must not stop the Macro Desk
        ("global", lambda: build_global(lib.view(today), params)),
        ("confirmers", lambda: build_confirmers(lib.view(today), latest["bias"])),
    ):
        try:
            write_json(macro / f"{name}.json", make(), indent=None)
        except Exception:
            log.exception("%s data failed", name)
    compact["sp500"] = month_closes(lib.view(today).series("yahoo/GSPC"), compact["months"])
    write_json(macro / "history.json", compact, indent=None)
    by_year: dict[str, list] = {}
    for s in snaps:
        by_year.setdefault(s["as_of"][:4], []).append(s)
    for year, items in by_year.items():
        write_json(macro / "snapshots" / f"{year}.json", items, indent=None)
    update_log(macro / "log.csv", latest)
    try:  # the Evidence page reads the history; a bug there must not stop the Macro Desk
        log_start = (macro / "log.csv").read_text(encoding="utf-8").splitlines()[1].split(",")[0]
        names = {s["id"]: s["name"] for s in latest["signals"]}
        write_json(
            macro / "evidence.json", build_evidence(lib.view(today), compact, names, log_start), indent=None
        )
    except Exception:
        log.exception("evidence data failed")
    log.info(
        "macro: bias %s (%s) from %d of %d signals; %d monthly snapshots",
        latest["bias"]["score"],
        latest["bias"]["label"],
        latest["bias"]["used"],
        latest["bias"]["total"],
        len(snaps),
    )
    return latest
