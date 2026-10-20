import pytest
from conftest import FakeResponse, FakeSession, fixture_json

from pipeline.fetchers import yahoo
from pipeline.http import FetchError, HttpClient

DURING_SESSION = 1792510000  # 2026-10-20 15:46 UTC, New York session open
AFTER_CLOSE = 1792530000  # 2026-10-20 21:00 UTC


def chart_http(payload):
    return HttpClient(session=FakeSession([FakeResponse(200, payload)]), sleep=lambda s: None)


def test_chart_api_rows_use_exchange_dates_and_adjusted_close():
    payload = yahoo.via_chart_api("SPY", chart_http(fixture_json("yahoo_chart_spy.json")), now=AFTER_CLOSE)
    assert payload["via"] == "chart-api"
    assert payload["rows"][0] == ["2026-10-15", 760.5, 758.9]
    assert payload["meta"]["session_end"] == 1792526400


def test_bar_of_a_session_still_trading_is_dropped():
    payload = yahoo.via_chart_api("SPY", chart_http(fixture_json("yahoo_chart_spy.json")))
    data = yahoo.normalize(payload, now=DURING_SESSION)
    assert data.last_date == "2026-10-19"
    assert data.rows == [["2026-10-15", 760.5, 758.9], ["2026-10-19", 766.48, 766.48]]  # null close skipped


def test_bar_is_kept_after_the_close():
    payload = yahoo.via_chart_api("SPY", chart_http(fixture_json("yahoo_chart_spy.json")))
    data = yahoo.normalize(payload, now=AFTER_CLOSE)
    assert data.last_date == "2026-10-20"
    assert data.columns == ["date", "close", "adj_close"]
    assert data.meta["units"] == "USD"


def test_chart_api_error_is_reported():
    http = chart_http(
        {"chart": {"result": None, "error": {"description": "No data found, symbol may be delisted"}}}
    )
    with pytest.raises(FetchError, match="delisted"):
        yahoo.via_chart_api("NOPE", http)


def test_falls_back_to_chart_api_when_yfinance_breaks(monkeypatch):
    def broken(symbol):
        raise RuntimeError("Yahoo changed its cookies again")

    monkeypatch.setattr(yahoo, "via_yfinance", broken)
    payload = yahoo.fetch("SPY", chart_http(fixture_json("yahoo_chart_spy.json")))
    assert payload["via"] == "chart-api"


def test_both_paths_failing_names_both_errors(monkeypatch):
    monkeypatch.setattr(yahoo, "via_yfinance", lambda s: (_ for _ in ()).throw(RuntimeError("yf down")))
    http = HttpClient(
        session=FakeSession([FakeResponse(404, {"chart": {"error": {"description": "Not Found"}}})]),
        sleep=lambda s: None,
    )
    with pytest.raises(FetchError) as info:
        yahoo.fetch("SPY", http)
    assert "yf down" in str(info.value) and "chart API" in str(info.value)


def test_no_completed_closes_is_an_error():
    with pytest.raises(FetchError):
        yahoo.normalize({"meta": {}, "rows": [["2026-10-19", None, None]]})
