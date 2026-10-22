"""University of Michigan Surveys of Consumers: sentiment index and its two halves (free CSV tables).

FRED's UMCSENT is published a month late and has no components; Anton reads the Expectations index first,
so the dashboard takes all three straight from the survey's own data tables.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from ..http import FetchError, HttpClient
from ..store import SeriesData

BASE_URL = "https://www.sca.isr.umich.edu/files/"
SERIES = {
    "ICS": ("tbmics.csv", "ICS_ALL", "Index of Consumer Sentiment"),
    "ICC": ("tbmiccice.csv", "ICC", "Index of Current Economic Conditions"),
    "ICE": ("tbmiccice.csv", "ICE", "Index of Consumer Expectations"),
}
MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        start=1,
    )
}


def fetch(series_id: str, http: HttpClient) -> dict[str, Any]:
    if series_id not in SERIES:
        raise FetchError(f"unknown UMich series {series_id}")
    filename, column, title = SERIES[series_id]
    return {"id": series_id, "column": column, "title": title, "csv": http.get_text(BASE_URL + filename)}


def normalize(payload: dict[str, Any]) -> SeriesData:
    reader = csv.DictReader(io.StringIO(payload["csv"]))
    column = payload["column"]
    if not reader.fieldnames or column not in reader.fieldnames:
        raise FetchError(f"UMich table has no column {column} (columns: {reader.fieldnames})")
    rows: dict[str, float] = {}
    for rec in reader:
        month = MONTHS.get((rec.get("Month") or "").strip().lower())
        year = (rec.get("YYYY") or "").strip()
        value = (rec.get(column) or "").strip()
        if not month or not year.isdigit() or not value:
            continue
        try:
            rows[f"{int(year):04d}-{month:02d}-01"] = float(value)
        except ValueError:
            continue
    if not rows:
        raise FetchError(f"no values for {column}")
    meta = {
        "title": payload["title"],
        "units": "Index 1966:Q1=100",
        "units_short": "Index",
        "frequency": "monthly",
        "seasonal_adjustment": "NSA",
    }
    return SeriesData(meta=meta, columns=["date", "value"], rows=[[d, rows[d]] for d in sorted(rows)])
