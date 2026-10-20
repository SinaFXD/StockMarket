"""Read and validate the hand-entered CSVs, with messages a non-programmer can act on.

Rules: a row with any error is left out (never guessed), both copies of a duplicated month are left out,
and a file whose header is wrong is not read at all. Everything else in the file is still used.
"""

from __future__ import annotations

import csv
import difflib
import io
import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ..config import MANUAL_GRACE_DAYS
from .releases import add_months, month_of
from .schemas import Column, ManualFile

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
MISSING_MARKERS = {"na", "n/a", "nan", "null", "none", "-", "--", "–", "—", "."}
MONTH_NAMES = {
    name.lower(): i
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}


@dataclass
class Issue:
    message: str
    line: int | None = None
    column: str | None = None

    def text(self) -> str:
        where = []
        if self.line:
            where.append(f"line {self.line}")
        if self.column:
            where.append(f"column '{self.column}'")
        prefix = ", ".join(where)
        return f"{prefix[0].upper()}{prefix[1:]}: {self.message}" if where else self.message

    def as_dict(self) -> dict[str, Any]:
        return {"line": self.line, "column": self.column, "message": self.message, "text": self.text()}


@dataclass
class ManualDataset:
    spec: ManualFile
    path: Path
    rows: list[dict[str, Any]] = field(default_factory=list)
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)


def _guess_month(text: str) -> str | None:
    s = text.strip()

    def ok(y: int, m: int) -> str | None:
        return f"{y:04d}-{m:02d}" if 1 <= m <= 12 and 1900 <= y <= 2100 else None

    if m := re.fullmatch(r"(\d{4})[-/.](\d{1,2})(?:[-/.]\d{1,2})?", s):  # 2026-9, 2026/09, 2026-09-01
        return ok(int(m[1]), int(m[2]))
    if m := re.fullmatch(r"(\d{4})(\d{2})", s):  # 202609
        return ok(int(m[1]), int(m[2]))
    if m := re.fullmatch(r"(\d{1,2})[-/.](\d{4})", s):  # 09/2026
        return ok(int(m[2]), int(m[1]))
    if m := re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s):  # Excel: 9/1/2026 or 1/9/2026
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        return ok(y, a) if b == 1 else ok(y, b) if a == 1 else None
    if m := re.fullmatch(r"([A-Za-z]{3,9})[\s\-/.,']*(\d{2}|\d{4})", s):  # Sep 2026, Sep-26
        y = int(m[2]) + (2000 if len(m[2]) == 2 else 0)
        return ok(y, MONTH_NAMES[m[1].lower()]) if m[1].lower() in MONTH_NAMES else None
    if m := re.fullmatch(r"(\d{4})[\s\-/]+([A-Za-z]{3,9})", s):  # 2026 Sep
        return ok(int(m[1]), MONTH_NAMES[m[2].lower()]) if m[2].lower() in MONTH_NAMES else None
    return None


def parse_month(text: str) -> tuple[str | None, str | None]:
    s = text.strip()
    if not s:
        return None, "the month is empty; every row needs a month like 2026-09"
    if MONTH_RE.fullmatch(s):
        return s, None
    guess = _guess_month(s)
    hint = (
        f"did you mean {guess}?"
        if guess and guess != s
        else "write it like 2026-09 (year, dash, 2-digit month)"
    )
    return None, f"'{s}' is not a month in YYYY-MM format; {hint}"


def parse_number(text: str, col: Column) -> tuple[float | None, str | None, str | None]:
    """Return ``(value, error, warning)``."""
    s = text.strip()
    if not s:
        return None, None, None
    if s.lower() in MISSING_MARKERS:
        return None, None, f"'{s}' was read as an empty cell; for a missing value just leave the cell empty"
    if s.endswith("%"):
        return None, f"remove the % sign: write {s.rstrip('%').strip()} instead of {s}", None
    try:
        value = float(s.replace("−", "-"))  # accept the Unicode minus sign copied from PDFs
    except ValueError:
        hint = " Use a dot for decimals (48.7, not 48,7)." if "," in s else ""
        return None, f"'{s}' is not a number.{hint}", None
    if not math.isfinite(value):
        return None, f"'{s}' is not a number", None
    if col.min is not None and col.max is not None and not col.min <= value <= col.max:
        return (
            None,
            (
                f"{s} is outside the allowed range {col.min:g} to {col.max:g} for {col.label or col.name}; "
                "check for a typo"
            ),
            None,
        )
    return value, None, None


def _read_rows(text: str) -> list[tuple[int, list[str]]]:
    reader = csv.reader(io.StringIO(text, newline=""))
    rows: list[tuple[int, list[str]]] = []
    start = 1
    for row in reader:
        rows.append((start, row))
        start = reader.line_num + 1
    return rows


def _check_header(spec: ManualFile, header: list[str]) -> list[Issue]:
    expected = spec.column_names
    names = [h.strip().lower() for h in header]
    issues: list[Issue] = []
    for name in sorted({n for n in names if names.count(n) > 1}):
        issues.append(Issue(f"column '{name}' appears more than once in the header", line=1))
    for name in [n for n in names if n not in expected]:
        close = difflib.get_close_matches(name, expected, n=1)
        hint = f" Did you mean '{close[0]}'?" if close else ""
        issues.append(Issue(f"unknown column '{name}' in the header.{hint}", line=1))
    missing = [n for n in expected if n not in names]
    if missing:
        issues.append(Issue(f"the header is missing column(s): {', '.join(missing)}", line=1))
    if issues:
        issues.append(Issue("the first line must be exactly: " + ",".join(expected), line=1))
    return issues


def _month_ranges(months: list[str]) -> list[tuple[str, str]]:
    gaps = []
    for a, b in zip(months, months[1:], strict=False):
        if (first := add_months(a, 1)) != b:
            gaps.append((first, add_months(b, -1)))
    return gaps


def load(spec: ManualFile, path: Path, today: date) -> ManualDataset:
    ds = ManualDataset(spec=spec, path=path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        ds.errors.append(Issue(f"file {spec.filename} is missing from data/manual/"))
        return ds
    except UnicodeDecodeError:
        ds.errors.append(Issue("the file is not plain UTF-8 text; save it as CSV (UTF-8)"))
        return ds

    rows = [(n, r) for n, r in _read_rows(text) if any(cell.strip() for cell in r)]
    if not rows:
        ds.errors.append(
            Issue(
                "the file is completely empty; the first line must be the header: "
                + ",".join(spec.column_names)
            )
        )
        return ds
    header_line, header = rows[0]
    if issues := _check_header(spec, header):
        ds.errors.extend(issues)
        return ds
    names = [h.strip().lower() for h in header]
    columns = {c.name: c for c in spec.columns}
    this_month = month_of(today)

    parsed: list[tuple[int, dict[str, Any]]] = []
    for line, raw in rows[1:]:
        if len(raw) != len(names):
            ds.errors.append(
                Issue(
                    f"this row has {len(raw)} values but the header has {len(names)} columns. "
                    "Check for a missing or extra comma (decimals must use a dot, e.g. 48.7; "
                    "put text containing commas in double quotes).",
                    line=line,
                )
            )
            continue
        record: dict[str, Any] = {}
        row_errors: list[Issue] = []
        for name, cell in zip(names, raw, strict=True):
            col = columns[name]
            value: Any = None
            if col.kind == "month":
                value, err = parse_month(cell)
                if value and value > this_month:
                    value, err = None, f"{value} is in the future (today is {today.isoformat()})"
                if err:
                    row_errors.append(Issue(err, line=line, column=name))
            elif col.is_value:
                value, err, warn = parse_number(cell, col)
                if err:
                    row_errors.append(Issue(err, line=line, column=name))
                if warn:
                    ds.warnings.append(Issue(warn, line=line, column=name))
            elif col.kind == "choice":
                value = cell.strip().lower() or None
                if value and value not in col.choices:
                    row_errors.append(
                        Issue(
                            f"'{cell.strip()}' is not allowed; use one of: " + ", ".join(col.choices),
                            line=line,
                            column=name,
                        )
                    )
                    value = None
            elif col.kind == "rank":
                s = cell.strip()
                if s:
                    if s.isdigit() and int(s) >= 1:
                        value = int(s)
                    else:
                        row_errors.append(
                            Issue(f"'{s}' must be a whole number (1, 2, 3, ...)", line=line, column=name)
                        )
            else:
                value = cell.strip() or None
            if col.required and value is None and not any(e.column == name for e in row_errors):
                row_errors.append(Issue("this cell must not be empty", line=line, column=name))
            record[name] = value
        if row_errors:
            ds.errors.extend(row_errors)
            continue
        value_cols = [c.name for c in spec.columns if c.is_value]
        if value_cols and all(record[c] is None for c in value_cols):
            ds.warnings.append(
                Issue(f"the row for {record['month']} has no values and was skipped", line=line)
            )
            continue
        parsed.append((line, record))

    by_key: dict[tuple, list[int]] = {}
    for line, record in parsed:
        by_key.setdefault(tuple(record[k] for k in spec.key), []).append(line)
    for key, lines in by_key.items():
        if len(lines) > 1:
            what = " / ".join(str(k) for k in key)
            ds.errors.append(
                Issue(
                    f"{what} appears {len(lines)} times (lines {', '.join(map(str, lines))}). "
                    "Keep only one row; until then none of them is used.",
                    line=lines[-1],
                )
            )
    good = [r for line, r in parsed if len(by_key[tuple(r[k] for k in spec.key)]) == 1]

    def sort_key(r: dict[str, Any]) -> tuple:
        return tuple((r[k] is None, r[k] if r[k] is not None else 0) for k in spec.sort)

    ds.rows = sorted(good, key=sort_key)
    if spec.key == ("month",):
        for first, last in _month_ranges([r["month"] for r in ds.rows]):
            span = first if first == last else f"{first} to {last}"
            ds.warnings.append(
                Issue(f"no valid row for {span}; add or fix the missing month(s) when you can")
            )
    if spec.name == "ism_industries":
        seen: dict[tuple, int] = {}
        for r in ds.rows:
            if r["rank"] is not None:
                k = (r["month"], r["report"], r["status"], r["rank"])
                if k in seen:
                    ds.warnings.append(
                        Issue(
                            f"rank {r['rank']} is used twice in the {r['month']} {r['report']} "
                            f"{r['status']} list"
                        )
                    )
                seen[k] = 1
    return ds


def freshness(ds: ManualDataset, today: date, grace_days: int = MANUAL_GRACE_DAYS) -> dict[str, Any]:
    """Per tracked column: last month entered vs the latest report that should be out by ``today``.

    ``ok`` = up to date; ``due`` = a newer report is out and can still be entered within the grace
    period; ``awaiting`` = no data, or the latest report is missing for longer than the grace period. An
    ``awaiting`` indicator is shown with its last date and left out of the scores.
    """
    tracked = []
    for t in ds.spec.tracked:
        months = [r["month"] for r in ds.rows if r.get(t.column) is not None]
        last = max(months) if months else None
        expected = t.release.latest_released_month(today)
        info: dict[str, Any] = {
            "column": t.column,
            "label": t.label,
            "last_month": last,
            "expected_month": expected,
            "release_rule": t.release.describe(),
            "next_month": add_months(expected, 1),
            "next_due": t.release.due_date(add_months(expected, 1)).isoformat(),
        }
        if last is None:
            info.update(status="awaiting", reason="no data entered yet")
        elif last >= expected:
            info.update(status="ok", reason=f"up to date ({last})")
        else:
            missing_month = add_months(last, 1)
            due = t.release.due_date(missing_month)
            late = (today - due).days
            info["missing_since"] = due.isoformat()
            if late <= grace_days:
                info.update(
                    status="due",
                    reason=f"{missing_month} report out since ~{due.isoformat()}; "
                    f"please enter it (last entry {last})",
                )
            else:
                info.update(
                    status="awaiting",
                    reason=f"last entry {last}; the {missing_month} report has been "
                    f"out since ~{due.isoformat()}",
                )
        tracked.append(info)
    order = {"ok": 0, "due": 1, "awaiting": 2}
    if tracked:
        status = max((t["status"] for t in tracked), key=order.__getitem__)
    else:
        status = "ok" if ds.rows else "empty"
    months = sorted({r["month"] for r in ds.rows})
    return {
        "status": status,
        "tracked": tracked,
        "rows": len(ds.rows),
        "first_month": months[0] if months else None,
        "last_month": months[-1] if months else None,
    }
