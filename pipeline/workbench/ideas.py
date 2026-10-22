"""Trade ideas saved in the repository: ``data/ideas/<TICKER>.md`` (lesson 33's template, the parts only the user
can fill). The website writes these files (button "Publish to GitHub"); this module reads and checks them and
publishes ``site/data/ideas.json``.

File format: a YAML header between ``---`` lines, then one ``## Heading`` per note::

    ---
    side: long             # long | short
    status: researching    # researching | ready | active | closed | dropped
    opened: 2026-10-22
    updated: 2026-10-22
    horizon_days: 40       # the course's window is 20-60 days
    structure: stock       # stock | margin | cfd
    entry_price: 239.34    # optional
    assumptions:           # optional: your own numbers for the price targets
      pe: 120
    ---

    ## Business
    ...
    ## Catalysts
    - 2026-11-05: Investor day

The ticker is the file name (so tickers such as ON or Y are never read as YAML booleans).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

SIDES = ("long", "short")
STATUSES = ("researching", "ready", "active", "closed", "dropped")
STRUCTURES = ("stock", "margin", "cfd")
ASSUMPTIONS = ("pe", "ps", "eps1", "eps2", "sales1", "sales2", "shares")
# heading -> key (headings are matched without case)
SECTIONS = {
    "business": "business",
    "kpis and management plan": "kpis",
    "industry drivers": "drivers",
    "catalysts": "catalysts",
    "timing and technicals": "timing",
    "structure": "structure_why",
    "review notes": "notes",
}
TEXT_KEYS = [k for k in SECTIONS.values() if k != "catalysts"]
TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")
CATALYST = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*[:\-–]\s*(.*)$")


class IdeaError(ValueError):
    pass


def _date(v: Any, field: str, problems: list[str]) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    try:
        return date.fromisoformat(str(v).strip()).isoformat()
    except ValueError:
        problems.append(f"{field}: '{v}' is not a date like 2026-10-22")
        return None


def _number(v: Any, field: str, problems: list[str]) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        problems.append(f"{field}: '{v}' is not a number")
        return None
    try:
        x = float(str(v).replace(",", ""))
    except ValueError:
        problems.append(f"{field}: '{v}' is not a number")
        return None
    if x != x or x <= 0:
        problems.append(f"{field}: must be a positive number")
        return None
    return x


def _choice(v: Any, field: str, options: tuple[str, ...], default: str, problems: list[str]) -> str:
    if v is None or v == "":
        return default
    s = str(v).strip().lower()
    if s not in options:
        problems.append(f"{field}: '{v}' must be one of {', '.join(options)}")
        return default
    return s


def split(text: str) -> tuple[str, str]:
    """Header and body of an idea file."""
    lines = text.replace("\r\n", "\n").lstrip("﻿").split("\n")
    if not lines or lines[0].strip() != "---":
        raise IdeaError("the file must start with a line '---' (the header)")
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    raise IdeaError("the header is not closed: add a line '---' after it")


def sections(body: str) -> tuple[dict[str, str], list[str]]:
    out: dict[str, list[str]] = {}
    unknown: list[str] = []
    key = None
    for line in body.split("\n"):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and m.group(1).strip().lower() in SECTIONS:
            key = SECTIONS[m.group(1).strip().lower()]
            out.setdefault(key, [])
            continue
        if m and key is None:
            unknown.append(m.group(1).strip())
            continue
        if key is not None:
            out[key].append(line)
        elif line.strip():
            unknown.append(line.strip()[:40])
    return {k: "\n".join(v).strip() for k, v in out.items()}, unknown


def catalysts(text: str) -> list[dict[str, str | None]]:
    out = []
    for line in text.split("\n"):
        item = re.sub(r"^\s*[-*]\s*", "", line).strip()
        if not item:
            continue
        m = CATALYST.match(item)
        out.append({"date": m.group(1), "text": m.group(2).strip()} if m else {"date": None, "text": item})
    return out


def parse(text: str, ticker: str) -> tuple[dict[str, Any], list[str], list[str]]:
    """One idea file -> (idea, errors, warnings). Errors are problems the user must fix; the idea keeps every
    field that is valid."""
    errors: list[str] = []
    warnings: list[str] = []
    head_text, body = split(text)
    try:
        head = yaml.safe_load(head_text) or {}
    except yaml.YAMLError as exc:
        raise IdeaError(f"the header is not valid YAML: {str(exc).splitlines()[0]}") from None
    if not isinstance(head, dict):
        raise IdeaError("the header must be lines like 'side: long'")
    known = {"ticker", "side", "status", "opened", "updated", "horizon_days", "structure", "entry_price"}
    known |= {"assumptions"}
    for k in head:
        if k not in known:
            warnings.append(f"unknown header field '{k}' (ignored)")
    if head.get("ticker") not in (None, "") and str(head["ticker"]).upper() != ticker:
        errors.append(f"ticker: '{head['ticker']}' does not match the file name {ticker}.md")
    idea: dict[str, Any] = {
        "ticker": ticker,
        "side": _choice(head.get("side"), "side", SIDES, "long", errors),
        "status": _choice(head.get("status"), "status", STATUSES, "researching", errors),
        "opened": _date(head.get("opened"), "opened", errors),
        "updated": _date(head.get("updated"), "updated", errors),
        "structure": _choice(head.get("structure"), "structure", STRUCTURES, "stock", errors),
        "entry_price": _number(head.get("entry_price"), "entry_price", errors),
        "horizon_days": None,
        "assumptions": {},
    }
    h = head.get("horizon_days")
    if h not in (None, ""):
        try:
            idea["horizon_days"] = int(h)
            if not 1 <= idea["horizon_days"] <= 365:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"horizon_days: '{h}' must be a whole number of days")
            idea["horizon_days"] = None
        else:
            if not 20 <= idea["horizon_days"] <= 60:
                warnings.append(f"horizon_days: {h} is outside the course's 20-60 day window")
    a = head.get("assumptions") or {}
    if not isinstance(a, dict):
        errors.append("assumptions: must be lines like '  pe: 25' under 'assumptions:'")
        a = {}
    for k, v in a.items():
        if k not in ASSUMPTIONS:
            warnings.append(f"assumptions.{k}: unknown (use {', '.join(ASSUMPTIONS)})")
            continue
        x = _number(v, f"assumptions.{k}", errors)
        if x is not None:
            idea["assumptions"][k] = x
    if idea["opened"] and idea["updated"] and idea["updated"] < idea["opened"]:
        warnings.append("updated is before opened")
    notes, unknown = sections(body)
    for u in unknown:
        warnings.append(f"text outside the known sections ignored: '{u}'")
    for k in TEXT_KEYS:
        idea[k] = notes.get(k, "")
    idea["catalysts"] = catalysts(notes.get("catalysts", ""))
    return idea, errors, warnings


def load(ideas_dir: Path) -> dict[str, Any]:
    """Every ``data/ideas/*.md`` file: the ideas, and the problems per file."""
    ideas, problems = [], []
    for path in sorted(ideas_dir.glob("*.md")) if ideas_dir.is_dir() else []:
        if path.name.lower() == "readme.md":
            continue
        ticker = path.stem.upper()
        if not TICKER.match(ticker):
            problems.append({"file": path.name, "errors": [f"'{path.stem}' is not a ticker"], "warnings": []})
            continue
        try:
            idea, errors, warnings = parse(path.read_text(encoding="utf-8"), ticker)
        except IdeaError as exc:
            problems.append({"file": path.name, "errors": [str(exc)], "warnings": []})
            continue
        ideas.append(idea)
        if errors or warnings:
            problems.append({"file": path.name, "errors": errors, "warnings": warnings})
    return {"ideas": ideas, "problems": problems}
