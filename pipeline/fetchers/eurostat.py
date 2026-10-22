"""Eurostat business and consumer surveys (JSON-stat API): euro-area Economic Sentiment Indicator.

The euro area grows over time (EA20, EA21, ...); the fetcher always takes the largest ``EA<n>`` aggregate
that has data, which Eurostat back-calculates for the whole history.
"""

from __future__ import annotations

import re
from typing import Any

from ..http import FetchError, HttpClient
from ..store import SeriesData

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
SERIES = {
    "ESI_EA": {
        "dataset": "ei_bssi_m_r2",
        "params": {"indic": "BS-ESI-I", "s_adj": "SA"},
        "geo": "euro_area",
        "title": "Economic Sentiment Indicator, euro area (seasonally adjusted, long-term average = 100)",
        "units_short": "Index",
    },
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
    spec = SERIES.get(series_id)
    if spec is None:
        raise FetchError(f"unknown Eurostat series {series_id}")
    data = http.get_json(BASE_URL + spec["dataset"], dict(spec["params"]))
    try:
        by_geo = _series_by_geo(data)
    except (KeyError, ValueError, TypeError) as exc:
        raise FetchError(f"unexpected Eurostat response: {exc}") from None
    candidates = sorted((int(m[1]), g) for g in by_geo if (m := EURO_AREA.match(g)) and by_geo[g])
    if not candidates:
        raise FetchError(f"no euro-area aggregate in Eurostat {spec['dataset']}")
    geo = candidates[-1][1]
    rows = [[f"{p}-01", v] for p, v in sorted(by_geo[geo].items())]
    return {"id": series_id, "geo": geo, "updated": data.get("updated"), "rows": rows}


def normalize(payload: dict[str, Any]) -> SeriesData:
    spec = SERIES.get(payload.get("id", ""), {})
    rows = [[d, v] for d, v in payload.get("rows", []) if v is not None]
    if not rows:
        raise FetchError("no observations")
    meta = {
        "title": f"{spec.get('title', payload.get('id'))} [{payload.get('geo')}]",
        "units": spec.get("units_short"),
        "units_short": spec.get("units_short"),
        "frequency": "monthly",
        "seasonal_adjustment": "SA",
        "source_updated": payload.get("updated"),
    }
    return SeriesData(meta=meta, columns=["date", "value"], rows=rows)
