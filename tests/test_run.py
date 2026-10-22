"""End-to-end behaviour of the runner with fake sources: last good copy, publishing, redaction."""

import json
from datetime import date

from conftest import fixture_json

from pipeline import run
from pipeline.catalog import CatalogEntry
from pipeline.fetchers import fred, yahoo
from pipeline.http import FetchError
from pipeline.store import read_series

SECRET = "0123456789abcdef0123456789abcdef"
FRED_ENTRY = CatalogEntry("fred", "DGS10", "US 10y", "money_markets")
CPI_ENTRY = CatalogEntry("fred", "CPIAUCSL", "CPI", "money_markets", vintages=True)
YAHOO_ENTRY = CatalogEntry("yahoo", "SPY", "SPY", "prices_fx_equities")


class FakeFredClient(fred.FredClient):
    def __init__(self, fail: bool = False):
        super().__init__(SECRET)
        self.fail = fail

    def series_info(self, series_id):
        if self.fail:
            raise FetchError(f"network error for https://api.stlouisfed.org/?api_key={SECRET}")
        return fixture_json("fred_series_dgs10.json")["seriess"][0]

    def observations(self, series_id):
        return [[o["date"], o["value"]] for o in fixture_json("fred_observations_dgs10.json")["observations"]]

    def vintages(self, series_id):
        return [["2026-09-01", "2026-10-14", "9999-12-31", "336.3"]]


def runner(tmp_path, **kw):
    return run.Runner(
        raw_dir=tmp_path / "raw", out_dir=tmp_path / "site", now_iso="2026-10-20T22:30:00Z", **kw
    )


def test_fresh_fetch_publishes_and_caches(tmp_path):
    r = runner(tmp_path, fred_client=FakeFredClient())
    res = r.update(FRED_ENTRY)
    assert (res.fetch_status, res.data_from, res.data.last_date) == ("ok", "fresh", "2026-10-16")
    published = read_series(tmp_path / "site" / "series" / "fred" / "DGS10.json")
    assert published.meta["label"] == "US 10y" and published.meta["fetched_at"] == "2026-10-20T22:30:00Z"
    assert (tmp_path / "raw" / "fred" / "DGS10.json").exists()


def test_failed_fetch_falls_back_to_raw_cache_then_to_published_copy(tmp_path):
    runner(tmp_path, fred_client=FakeFredClient()).update(FRED_ENTRY)

    res = runner(tmp_path, fred_client=FakeFredClient(fail=True)).update(FRED_ENTRY)
    assert (res.fetch_status, res.data_from, res.data.last_date) == ("failed", "raw-cache", "2026-10-16")

    (tmp_path / "raw" / "fred" / "DGS10.json").unlink()  # e.g. a fresh CI runner without the cache
    res = runner(tmp_path, fred_client=FakeFredClient(fail=True)).update(FRED_ENTRY)
    assert (res.fetch_status, res.data_from, res.data.last_date) == ("failed", "published", "2026-10-16")
    assert SECRET not in res.error


def test_vintages_are_cached_for_backtests(tmp_path):
    res = runner(tmp_path, fred_client=FakeFredClient()).update(CPI_ENTRY)
    assert res.vintages["status"] == "ok" and res.vintages["rows"] == 1
    assert res.vintages["latest_vintage"] == "2026-10-14"
    cached = json.loads((tmp_path / "raw" / "alfred" / "CPIAUCSL.json").read_text())
    assert cached["payload"]["rows"][0][3] == "336.3"


def test_yahoo_failure_without_any_copy_is_missing(tmp_path, monkeypatch):
    def down(symbol, http=None):
        raise FetchError("Yahoo is down")

    monkeypatch.setattr(yahoo, "fetch", down)
    res = runner(tmp_path, fred_client=FakeFredClient()).update(YAHOO_ENTRY)
    assert (res.fetch_status, res.data_from, res.data) == ("failed", "none", None)


def test_main_writes_health_and_manual_json_without_leaking_the_key(tmp_path, monkeypatch):
    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    for name, header in [
        (
            "ism_manufacturing",
            "month,pmi,new_orders,production,employment,supplier_deliveries,inventories,"
            "customers_inventories,prices,backlog,new_export_orders,imports",
        ),
        (
            "ism_services",
            "month,pmi,business_activity,new_orders,employment,supplier_deliveries,inventories,"
            "prices,backlog,new_export_orders,imports,inventory_sentiment",
        ),
        ("ism_industries", "month,report,industry,status,rank,comment"),
        (
            "nfib_sbet",
            "month,optimism_index,plans_employment,plans_capex,plans_inventories,"
            "expect_economy_improve,expect_real_sales_higher,current_inventory,current_job_openings,"
            "expected_credit_conditions,good_time_to_expand,earnings_trends",
        ),
        (
            "china_pmi",
            "month,nbs_manufacturing,nbs_non_manufacturing,ratingdog_manufacturing,ratingdog_services",
        ),
    ]:
        (manual_dir / f"{name}.csv").write_text(header + "\n")
    (manual_dir / "ism_manufacturing.csv").write_text(
        (manual_dir / "ism_manufacturing.csv").read_text()
        + "2026-09,49.1,48.9,50.2,45.3,52,47.9,45.1,62.1,46,47,49.5\n"
    )
    ideas_dir = tmp_path / "ideas"
    ideas_dir.mkdir()
    (ideas_dir / "ABC.md").write_text("---\nside: short\nstatus: active\n---\n## Business\nWidgets.\n")
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("fred:\n  - {id: DGS10, label: US 10y, block: money_markets}\n")
    monkeypatch.setattr(run.fred, "FredClient", lambda key: FakeFredClient(fail=True))
    monkeypatch.setenv("FRED_API_KEY", SECRET)

    code = run.main(
        [
            "--today",
            "2026-10-20",
            "--raw-dir",
            str(tmp_path / "raw"),
            "--out-dir",
            str(tmp_path / "site"),
            "--manual-dir",
            str(manual_dir),
            "--catalog",
            str(catalog),
            "--ideas-dir",
            str(ideas_dir),
            "--only",
            "fred",  # calendar and screener use their (empty) caches: no network in tests
        ]
    )
    assert code == 0
    health_text = (tmp_path / "site" / "health.json").read_text()
    assert SECRET not in health_text
    health = json.loads(health_text)
    assert health["series"][0]["status"] == "missing"
    assert health["today"] == date(2026, 10, 20).isoformat()
    ism = {m["name"]: m for m in health["manual"]}["ism_manufacturing"]
    assert ism["status"] == "ok" and ism["last_month"] == "2026-09"
    site_ism = json.loads((tmp_path / "site" / "manual" / "ism_manufacturing.json").read_text())
    assert site_ism["rows"][0][:2] == ["2026-09", 49.1]
    assert health["screener"]["stocks"] == 0 and health["calendar"]["events"] > 0
    assert health["ideas"] == {"status": "ok", "ideas": 1, "errors": 0, "warnings": 0}
    ideas = json.loads((tmp_path / "site" / "ideas.json").read_text())
    assert ideas["ideas"][0]["side"] == "short" and ideas["ideas"][0]["business"] == "Widgets."


def test_repeated_problems_become_one_annotation(monkeypatch, capsys, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    problem = {
        "status": "missing",
        "last_date": None,
        "age_days": None,
        "max_age_days": 10,
        "fetch": {"error": "FRED_API_KEY is not set"},
    }
    health = {
        "summary": {
            "series": {"total": 7, "ok": 0, "stale": 0, "failed": 0, "missing": 7},
            "manual": {"ok": 0, "due": 0, "awaiting": 0, "files_with_errors": 0},
        },
        "series": [dict(problem, key=f"fred/S{i}", label=f"S{i}") for i in range(7)],
    }
    run._report(health)
    annotations = [line for line in capsys.readouterr().out.splitlines() if line.startswith("::warning")]
    assert len(annotations) == 1
    assert (
        "7 series missing - FRED_API_KEY is not set: fred/S0" in annotations[0]
        and "and 2 more" in annotations[0]
    )
    assert "| fred/S6 | missing | - | FRED_API_KEY is not set |" in summary.read_text()
