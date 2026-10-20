from datetime import date

import pytest

from pipeline.catalog import BLOCKS, CatalogEntry, load_catalog
from pipeline.health import SeriesResult, build_health, series_entry, spark
from pipeline.store import SeriesData

TODAY = date(2026, 10, 20)


def test_real_catalog_is_consistent():
    entries = load_catalog()
    assert len(entries) >= 70
    assert len({e.key for e in entries}) == len(entries)
    assert all(e.block in BLOCKS for e in entries)
    assert all(e.vintages is False for e in entries if e.source == "yahoo")


@pytest.mark.parametrize("symbol, name", [("^GSPC", "GSPC"), ("CL=F", "CL_F"), ("000001.SS", "000001_SS")])
def test_file_names_are_safe(symbol, name):
    assert CatalogEntry("yahoo", symbol, "x", "prices_fx_equities").name == name


def test_catalog_rejects_unknown_blocks_and_yahoo_vintages(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text("fred:\n  - {id: X, label: x, block: nowhere}\n")
    with pytest.raises(ValueError, match="unknown block"):
        load_catalog(bad)
    bad.write_text("yahoo:\n  - {id: SPY, label: x, block: prices_fx_equities, vintages: true}\n")
    with pytest.raises(ValueError, match="only available for FRED"):
        load_catalog(bad)


def daily(last="2026-10-16", n=800):
    days = [date.fromordinal(date.fromisoformat(last).toordinal() - i).isoformat() for i in range(n)][::-1]
    return SeriesData(
        meta={"frequency": "daily"},
        columns=["date", "value"],
        rows=[[d, float(i)] for i, d in enumerate(days)],
    )


ENTRY = CatalogEntry("fred", "DGS10", "US 10y", "money_markets")


@pytest.mark.parametrize(
    "data, fetch_status, expected",
    [
        (daily(), "ok", "ok"),
        (daily(), "unchanged", "ok"),
        (daily(last="2026-10-01"), "ok", "stale"),  # 19 days old, limit 10 for daily series
        (daily(), "failed", "failed"),  # fetch failed: last good copy shown, flagged
        (None, "failed", "missing"),
    ],
)
def test_series_status(data, fetch_status, expected):
    entry = series_entry(SeriesResult(ENTRY, data, fetch_status, "fresh"), TODAY)
    assert entry["status"] == expected


def test_catalog_override_of_staleness_limit():
    slow = CatalogEntry("fred", "PCOPPUSDM", "Copper", "prices_fx_equities", max_age_days=140)
    data = SeriesData(meta={"frequency": "monthly"}, columns=["date", "value"], rows=[["2026-07-01", 9800.0]])
    entry = series_entry(SeriesResult(slow, data, "ok", "fresh"), TODAY)
    assert entry["age_days"] == 111 and entry["max_age_days"] == 140 and entry["status"] == "ok"


def test_spark_is_short_and_ends_on_the_last_value():
    data = daily()
    points = spark(data)
    assert len(points) == 60
    assert points[-1] == [data.last_date, data.last_value]
    assert points[0][0] >= "2024-10-16"


def test_health_summary_counts():
    results = [
        SeriesResult(ENTRY, daily(), "ok", "fresh"),
        SeriesResult(ENTRY, None, "failed", "none", error="x"),
    ]
    manual = [{"status": "awaiting", "errors": [{"message": "bad"}]}, {"status": "ok", "errors": []}]
    health = build_health(results, manual, generated_at="2026-10-20T22:30:00Z", today=TODAY)
    assert health["summary"]["series"] == {"total": 2, "ok": 1, "stale": 0, "failed": 0, "missing": 1}
    assert health["summary"]["manual"]["awaiting"] == 1 and health["summary"]["manual"]["errors"] == 1
