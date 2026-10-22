"""OECD and Eurostat fetchers: one download per data flow, split into series."""

import pytest
from conftest import FakeResponse, FakeSession

from pipeline.fetchers import eurostat, oecd
from pipeline.http import FetchError, HttpClient

OECD_CSV = """DATAFLOW,REF_AREA,FREQ,MEASURE,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE
X,JPN,M,IRLT,PA,2026-09,1.6
X,JPN,M,IRLT,PA,2026-08,1.5
X,JPN,M,IRSTCI,PA,2026-09,0.48
X,DEU,M,IRLT,PA,2026-09,2.7
X,DEU,M,IRLT,PA,2026-07,
"""


def client(*responses):
    session = FakeSession(list(responses))
    return HttpClient(session=session, sleep=lambda s: None), session


def test_oecd_splits_one_download_into_series():
    http, session = client(FakeResponse(200, None, text=OECD_CSV))
    jp = oecd.fetch("Y10_JP", http)
    assert jp["rows"] == [["2026-08-01", 1.5], ["2026-09-01", 1.6]]
    assert oecd.fetch("RATE_JP", http)["rows"] == [["2026-09-01", 0.48]]
    assert oecd.fetch("Y10_DE", http)["rows"] == [["2026-09-01", 2.7]]  # empty values skipped
    assert len(session.calls) == 1 and "DF_FINMARK" in session.calls[0][0]
    data = oecd.normalize(jp)
    assert data.meta["frequency"] == "monthly" and "Japan 10-year" in data.meta["title"]


def test_oecd_cpi_flows_and_unknown_ids():
    assert oecd._spec("CPI_JP")[0] == "prices2018" and oecd._spec("CPI_GB")[0] == "prices"
    assert oecd._spec("RATE_CN")[2] == "IR3TIB"  # China: 3m interbank, its overnight series ended
    with pytest.raises(FetchError):
        oecd.fetch("Y10_FR", client()[0])
    with pytest.raises(FetchError):
        oecd.normalize({"id": "Y10_JP", "rows": []})


def jsonstat(geos: dict[str, list[float | None]]) -> dict:
    times = ["2026-07", "2026-08", "2026-09"]
    values, i = {}, 0
    for vals in geos.values():
        for v in vals:
            if v is not None:
                values[str(i)] = v
            i += 1
    return {
        "id": ["geo", "time"],
        "size": [len(geos), len(times)],
        "dimension": {
            "geo": {"category": {"index": {g: k for k, g in enumerate(geos)}}},
            "time": {"category": {"index": {t: k for k, t in enumerate(times)}}},
        },
        "value": values,
        "updated": "2026-09-29",
    }


def test_eurostat_largest_euro_area_and_countries_share_one_request():
    body = jsonstat({"EA20": [95.0, 96.0, 97.0], "EA21": [95.5, 96.5, 97.5], "DE": [94.0, None, 95.0]})
    http, session = client(FakeResponse(200, body))
    ea = eurostat.fetch("ESI_EA", http)
    de = eurostat.fetch("ESI_DE", http)
    assert ea["geo"] == "EA21" and ea["rows"][-1] == ["2026-09-01", 97.5]
    assert de["rows"] == [["2026-07-01", 94.0], ["2026-09-01", 95.0]]
    assert len(session.calls) == 1 and session.calls[0][1]["indic"] == "BS-ESI-I"
    assert "Germany" in eurostat.normalize(de).meta["title"]


def test_eurostat_sector_series_use_their_own_indicator():
    http, session = client(FakeResponse(200, jsonstat({"EA21": [-8.0, -7.0, -6.5]})))
    payload = eurostat.fetch("ICI_EA", http)
    assert session.calls[0][1]["indic"] == "BS-ICI-BAL"
    assert eurostat.normalize(payload).meta["units"] == "Balance"
