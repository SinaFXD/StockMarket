import pytest
from conftest import FakeResponse, FakeSession, fixture_json

from pipeline.fetchers import fred
from pipeline.http import FetchError, HttpClient


class FakeFred:
    """Stands in for FredClient; counts how often observations are downloaded."""

    def __init__(self, last_updated="2026-10-19 15:16:46-05"):
        self.info = dict(fixture_json("fred_series_dgs10.json")["seriess"][0], last_updated=last_updated)
        self.observation_calls = 0
        self.vintage_calls = 0

    def series_info(self, series_id):
        return self.info

    def observations(self, series_id):
        self.observation_calls += 1
        return [[o["date"], o["value"]] for o in fixture_json("fred_observations_dgs10.json")["observations"]]

    def vintages(self, series_id):
        self.vintage_calls += 1
        return [["2026-08-01", "2026-09-11", "9999-12-31", "334.1"]]


def test_normalize_skips_missing_values_and_maps_frequency():
    payload, reused = fred.fetch(FakeFred(), "DGS10", cached=None)
    data = fred.normalize(payload)
    assert reused is False
    assert data.rows == [
        ["2026-10-13", 5.21],
        ["2026-10-14", 5.19],
        ["2026-10-15", 5.1],
        ["2026-10-16", 5.09],
    ]
    assert data.meta["frequency"] == "daily"
    assert data.meta["source_updated"] == "2026-10-19 15:16:46-05"


def test_integers_stay_integers():
    data = fred.normalize({"series": {"frequency_short": "M"}, "observations": [["2026-09-01", "159526"]]})
    assert data.rows == [["2026-09-01", 159526]]
    assert isinstance(data.rows[0][1], int)


def test_unchanged_series_reuses_cached_observations():
    client = FakeFred()
    first, _ = fred.fetch(client, "DGS10", cached=None)
    again, reused = fred.fetch(client, "DGS10", cached=first)
    assert reused is True
    assert client.observation_calls == 1
    assert again["observations"] == first["observations"]


def test_updated_series_is_downloaded_again():
    old, _ = fred.fetch(FakeFred(last_updated="2026-10-01 08:00:00-05"), "DGS10", cached=None)
    client = FakeFred()
    _, reused = fred.fetch(client, "DGS10", cached=old)
    assert reused is False and client.observation_calls == 1


def test_empty_series_is_an_error():
    with pytest.raises(FetchError):
        fred.normalize({"series": {}, "observations": [["2026-10-12", "."]]})


def test_missing_api_key_gives_a_helpful_error():
    with pytest.raises(FetchError, match="FRED_API_KEY"):
        fred.FredClient(api_key=None).series_info("DGS10")


def test_observations_are_paged(monkeypatch):
    monkeypatch.setattr(fred, "PAGE_LIMIT", 2)
    pages = [
        FakeResponse(
            200,
            {
                "count": 3,
                "observations": [{"date": "2026-01-01", "value": "1"}, {"date": "2026-02-01", "value": "2"}],
            },
        ),
        FakeResponse(200, {"count": 3, "observations": [{"date": "2026-03-01", "value": "3"}]}),
    ]
    session = FakeSession(pages)
    client = fred.FredClient("k" * 32, http=HttpClient(session=session, sleep=lambda s: None))
    assert client.observations("X") == [["2026-01-01", "1"], ["2026-02-01", "2"], ["2026-03-01", "3"]]
    assert [c[1]["offset"] for c in session.calls] == [0, 2]


# ALFRED: CPI for July 2026 first published 2026-08-12 as 332.8, revised to 332.9 on 2027-02-10.
VINTAGE_ROWS = [
    ["2026-07-01", "2026-08-12", "2027-02-09", "332.8"],
    ["2026-07-01", "2027-02-10", "9999-12-31", "332.9"],
    ["2026-08-01", "2026-08-12", "2026-09-10", "."],
    ["2026-08-01", "2026-09-11", "9999-12-31", "334.1"],
]


def test_as_known_on_rebuilds_the_series_of_a_past_day():
    assert fred.as_known_on(VINTAGE_ROWS, "2026-08-20") == [["2026-07-01", 332.8]]
    assert fred.as_known_on(VINTAGE_ROWS, "2026-10-01") == [["2026-07-01", 332.8], ["2026-08-01", 334.1]]
    assert fred.as_known_on(VINTAGE_ROWS, "2027-03-01") == [["2026-07-01", 332.9], ["2026-08-01", 334.1]]


def test_first_release_ignores_later_revisions():
    assert fred.first_release(VINTAGE_ROWS) == [
        ["2026-07-01", 332.8, "2026-08-12"],
        ["2026-08-01", 334.1, "2026-09-11"],
    ]


def test_vintages_are_only_downloaded_when_the_series_changed():
    client = FakeFred()
    payload, reused = fred.fetch_vintages(client, "CPIAUCSL", "2026-10-14 07:44:01-05", cached=None)
    assert reused is False
    _, reused = fred.fetch_vintages(client, "CPIAUCSL", "2026-10-14 07:44:01-05", cached=payload)
    assert reused is True and client.vintage_calls == 1
    _, reused = fred.fetch_vintages(client, "CPIAUCSL", "2026-11-13 07:44:01-05", cached=payload)
    assert reused is False and client.vintage_calls == 2
