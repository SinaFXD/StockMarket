"""OECD Data Explorer (SDMX REST, CSV): interest rates and CPI inflation for Japan, the UK, Germany, Italy and
China (lessons 4 and 14: "the same template applies" to other countries' money markets).

FRED's copies of these OECD series stopped updating in 2021-2025, so they come straight from the OECD.
Each data flow is downloaded once per run for all five countries (the OECD limits requests per hour);
the HTTP client keeps the response for the other series of the same flow.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from ..http import FetchError, HttpClient
from ..store import SeriesData

BASE_URL = "https://sdmx.oecd.org/public/rest/data/"
# flow id -> (dataflow, key). Keys are REF_AREA.FREQ.MEASURE... with "+" for several values.
FLOWS = {
    "finmark": ("OECD.SDD.STES,DSD_STES@DF_FINMARK,", "JPN+GBR+DEU+ITA+CHN.M.IR3TIB+IRLT+IRSTCI.PA....."),
    # national CPI, % change over 1 year; Japan and Italy are only current in the COICOP 2018 flow
    "prices": ("OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0", "GBR+DEU+CHN.M.N.CPI.PA._T.N.GY"),
    "prices2018": ("OECD.SDD.TPS,DSD_PRICES_COICOP2018@DF_PRICES_C2018_ALL,", "JPN+ITA.M.N.CPI.PA._T.N.GY"),
}
COUNTRIES = {"JP": "JPN", "GB": "GBR", "DE": "DEU", "IT": "ITA", "CN": "CHN"}
NAMES = {"JP": "Japan", "GB": "UK", "DE": "Germany", "IT": "Italy", "CN": "China"}
# Short rate: the overnight interbank rate (closest to each central bank's policy rate) except China, whose
# overnight series ended in 2025; there the 3-month interbank rate (SHIBOR) is used.
SHORT = {"JP": "IRSTCI", "GB": "IRSTCI", "DE": "IRSTCI", "IT": "IRSTCI", "CN": "IR3TIB"}
SHORT_LABEL = {"IRSTCI": "overnight interbank rate", "IR3TIB": "3-month interbank rate"}


def _spec(series_id: str) -> tuple[str, str, str, str]:
    """Series id -> (flow, area, measure, title). Ids: Y10_<cc>, RATE_<cc>, CPI_<cc>."""
    kind, _, cc = series_id.partition("_")
    if cc not in COUNTRIES or kind not in ("Y10", "RATE", "CPI"):
        raise FetchError(f"unknown OECD series {series_id}")
    name = NAMES[cc]
    if kind == "Y10":
        return "finmark", COUNTRIES[cc], "IRLT", f"{name} 10-year government bond yield (monthly average)"
    if kind == "RATE":
        m = SHORT[cc]
        return "finmark", COUNTRIES[cc], m, f"{name} {SHORT_LABEL[m]} (monthly average)"
    flow = "prices2018" if cc in ("JP", "IT") else "prices"
    return flow, COUNTRIES[cc], "CPI", f"{name} consumer prices, all items, % change over 1 year"


def fetch(series_id: str, http: HttpClient) -> dict[str, Any]:
    flow, area, measure, _ = _spec(series_id)
    dataflow, key = FLOWS[flow]
    text = http.get_text(f"{BASE_URL}{dataflow}/{key}", {"format": "csvfile"}, memo=True)
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = sorted(
            [r["TIME_PERIOD"] + "-01", float(r["OBS_VALUE"])]
            for r in reader
            if r.get("REF_AREA") == area and r.get("MEASURE") == measure and r.get("OBS_VALUE")
        )
    except (KeyError, ValueError) as exc:
        raise FetchError(f"unexpected OECD response: {exc}") from None
    return {"id": series_id, "flow": dataflow, "rows": rows}


def normalize(payload: dict[str, Any]) -> SeriesData:
    _, _, _, title = _spec(payload.get("id", ""))
    rows = [[d, v] for d, v in payload.get("rows", []) if v is not None]
    if not rows:
        raise FetchError("no observations")
    meta = {
        "title": title,
        "units": "Percent",
        "units_short": "%",
        "frequency": "monthly",
        "seasonal_adjustment": "NSA",
        "source_dataflow": payload.get("flow"),
    }
    return SeriesData(meta=meta, columns=["date", "value"], rows=rows)
