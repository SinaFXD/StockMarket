"""Eurostat business and consumer surveys (JSON-stat API): the Economic Sentiment Indicator for the euro area
and its big countries, and the euro-area sector confidence indicators (lesson 13).

One request per indicator returns every country; the HTTP client keeps it for the rest of the run.

The euro area grows over time (EA20, EA21, ...); the fetcher always takes the largest ``EA<n>`` aggregate
that has data, which Eurostat back-calculates for the whole history.
"""

from __future__ import annotations

import re
from typing import Any

from ..http import FetchError, HttpClient
from ..store import SeriesData

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
DATASET = "ei_bssi_m_r2"
# indicator code -> (title, unit). Confidence indicators are balances (% of positive minus negative answers).
INDICATORS = {
    "BS-ESI-I": ("Economic Sentiment Indicator (long-term average = 100)", "Index"),
    "BS-ICI-BAL": ("Industrial confidence indicator", "Balance"),
    "BS-SCI-BAL": ("Services confidence indicator", "Balance"),
    "BS-CSMCI-BAL": ("Consumer confidence indicator", "Balance"),
    "BS-RCI-BAL": ("Retail trade confidence indicator", "Balance"),
    "BS-CCI-BAL": ("Construction confidence indicator", "Balance"),
}
COUNTRIES = {"DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain", "NL": "Netherlands"}
SECTORS = {
    "ICI": "BS-ICI-BAL",
    "SCI": "BS-SCI-BAL",
    "CSMCI": "BS-CSMCI-BAL",
    "RCI": "BS-RCI-BAL",
    "CCI": "BS-CCI-BAL",
}
# Series id -> (indicator, geo). "euro_area" = the largest EA<n> aggregate.
SERIES = {
    "ESI_EA": ("BS-ESI-I", "euro_area"),
    **{f"ESI_{c}": ("BS-ESI-I", c) for c in COUNTRIES},
    **{f"{k}_EA": (code, "euro_area") for k, code in SECTORS.items()},
}
EURO_AREA = re.compile(r"^EA(\d+)$")


def _series_by_geo(data: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Unpack a JSON-stat 2.0 cube with one free ``geo`` and ``time`` dimension."""
    ids, sizes, dims = data["id"], data["size"], data["dimension"]
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    geo_index = dims["geo"]["category"]["index"]
    time_index = dims["time"]["category"]["index"]
    g_pos, t_pos = ids.index("geo"), ids.index("time")
    out: dict[str, dict[str, float]] = {}
    for geo, gi in geo_index.items():
        for period, ti in time_index.items():
            value = data["value"].get(str(gi * strides[g_pos] + ti * strides[t_pos]))
            if value is not None:
                out.setdefault(geo, {})[period] = float(value)
    return out


def fetch(series_id: str, http: HttpClient) -> dict[str, Any]:
    if series_id not in SERIES:
        raise FetchError(f"unknown Eurostat series {series_id}")
    indic, want = SERIES[series_id]
    data = http.get_json(BASE_URL + DATASET, {"indic": indic, "s_adj": "SA"}, memo=True)
    try:
        by_geo = _series_by_geo(data)
    except (KeyError, ValueError, TypeError) as exc:
        raise FetchError(f"unexpected Eurostat response: {exc}") from None
    if want == "euro_area":
        candidates = sorted((int(m[1]), g) for g in by_geo if (m := EURO_AREA.match(g)) and by_geo[g])
        if not candidates:
            raise FetchError(f"no euro-area aggregate in Eurostat {DATASET}")
        geo = candidates[-1][1]
    else:
        geo = want
    rows = [[f"{p}-01", v] for p, v in sorted(by_geo.get(geo, {}).items())]
    return {"id": series_id, "geo": geo, "updated": data.get("updated"), "rows": rows}


def normalize(payload: dict[str, Any]) -> SeriesData:
    indic, _ = SERIES.get(payload.get("id", ""), ("", ""))
    title, unit = INDICATORS.get(indic, (payload.get("id"), None))
    rows = [[d, v] for d, v in payload.get("rows", []) if v is not None]
    if not rows:
        raise FetchError("no observations")
    geo = payload.get("geo")
    meta = {
        "title": f"{title}, {COUNTRIES.get(geo, 'euro area')}, seasonally adjusted [{geo}]",
        "units": unit,
        "units_short": unit,
        "frequency": "monthly",
        "seasonal_adjustment": "SA",
        "source_updated": payload.get("updated"),
    }
    return SeriesData(meta=meta, columns=["date", "value"], rows=rows)
