"""Sector Screener: the 11 numbers, lesson-28 data checks, sector averages and the download/caching rules."""

from datetime import UTC, date, datetime

import pytest

from pipeline.config import SCREENER
from pipeline.http import FetchError
from pipeline.screener import numbers, yahoo
from pipeline.screener.build import ScreenerBuilder, status_of
from pipeline.store import RawCache

TODAY = date(2026, 10, 22)
NOW = datetime(2026, 10, 22, 6, 0, tzinfo=UTC)
P = dict(SCREENER)


def quote(sym, price=100.0, eps_cy=5.0, name=None, **kw):
    return {
        "symbol": sym,
        "longName": name or f"{sym} Inc.",
        "regularMarketPrice": price,
        "marketCap": 10e9,
        "currency": "USD",
        "financialCurrency": "USD",
        "epsCurrentYear": eps_cy,
        "epsForward": 6.0,
        "averageDailyVolume3Month": 1e6,
        "sector": "Technology",
        **kw,
    }


def summary(eps0=4.0, eps1=5.0, eps2=6.0, analysts=10, country="United States", ccy="USD"):
    return {
        "industry": "Software",
        "country": country,
        "currency": "USD",
        "0y": {"eps_year_ago": eps0, "eps": eps1, "analysts": analysts, "eps_currency": ccy, "end": "2026-12-31",
               "rev": 120.0, "rev_year_ago": 100.0, "eps_90d_ago": 4.0},
        "+1y": {"eps": eps2, "analysts": analysts, "rev": 132.0},
    }  # fmt: skip


def row(q=None, s=None, fetched="2026-10-22T05:00:00Z"):
    return numbers.compute(q or quote("ABC"), s if s is not None else summary(), fetched, TODAY, P)


def test_the_eleven_numbers():
    r = row()
    assert (r["price"], r["mcap"], r["eps0"], r["eps1"], r["eps2"]) == (100.0, 10e9, 4.0, 5.0, 6.0)
    assert r["eg1"] == pytest.approx(25.0) and r["eg2"] == pytest.approx(20.0)
    assert r["pe1"] == pytest.approx(20.0) and r["pe2"] == pytest.approx(100 / 6)
    assert r["peg1"] == pytest.approx(0.8) and r["peg2"] == pytest.approx((100 / 6) / 20)
    assert r["rg1"] == pytest.approx(20.0) and r["rg2"] == pytest.approx(10.0)
    assert r["eps1_rev90"] == pytest.approx(25.0) and r["fy"] == "2026-12" and r["flags"] == []


def test_course_rules_for_losses_and_negative_growth():
    loss = row(s=summary(eps0=-1.0, eps1=-0.5, eps2=0.8))
    assert loss["eg1"] is None  # growth from a loss is not a rate
    assert loss["pe1"] is None and loss["peg1"] is None  # P/E needs EPS > 0
    assert loss["eg2"] is None and loss["pe2"] == pytest.approx(125.0)
    assert {"negative_eps", "turnaround_base"} <= set(loss["flags"])
    falling = row(s=summary(eps0=5.0, eps1=4.0, eps2=3.0))
    assert (
        falling["eg1"] == pytest.approx(-20.0) and falling["peg1"] is None
    )  # PEG meaningless with falling EPS


def test_data_checks():
    assert "few_analysts" in row(s=summary(analysts=2))["flags"]
    assert "stale" in row(fetched="2026-10-01T00:00:00Z")["flags"]
    assert "extreme_growth" in row(s=summary(eps0=0.5, eps1=5.0))["flags"]
    assert "extreme_pe" in row(q=quote("X", price=2000.0))["flags"]
    assert "currency" in row(s=summary(ccy="TWD"))["flags"]
    assert "currency" in row(q=quote("Y", financialCurrency="CNY"))["flags"]
    assert "feed_mismatch" in row(q=quote("G", eps_cy=7.0))["flags"]  # screener says 7, estimates say 5
    abroad = row(s=summary(country="Ireland"))
    assert "foreign" in abroad["flags"] and numbers.included(abroad)  # reports in USD: kept in averages
    waiting = numbers.compute(quote("Z"), None, None, TODAY, P)
    assert "no_profile" in waiting["flags"] and waiting["eps1"] == 5.0 and not numbers.included(waiting)


def test_share_classes_keep_the_line_with_usable_numbers():
    good = row(q=quote("GOOG", name="Alphabet Inc.", averageDailyVolume3Month=1e6))
    bad = row(q=quote("GOOGL", name="Alphabet Inc.", eps_cy=9.0, averageDailyVolume3Month=5e6))
    other = row(q=quote("FBNC", name="First Bancorp", price=60.0), s=summary(eps0=2.0, eps1=3.0, eps2=3.5))
    other2 = row(q=quote("FBP", name="First BanCorp.", price=20.0), s=summary(eps0=1.5, eps1=1.8, eps2=2.0))
    rows = [good, bad, other, other2]
    numbers.mark_duplicates(rows)
    assert "duplicate" in bad["flags"] and bad["duplicate_of"] == "GOOG" and "duplicate" not in good["flags"]
    assert "duplicate" not in other["flags"] + other2["flags"]  # same name, different company


def test_group_stats_skip_excluded_rows_and_missing_values():
    rows = [
        row(),
        row(s=summary(eps0=4.0, eps1=4.4, eps2=4.84)),
        row(q=quote("L", eps_cy=1.0), s=summary(eps0=-1.0, eps1=1.0, eps2=2.0)),  # growth n/m, kept
        row(s=summary(ccy="EUR")),  # excluded
    ]
    st = numbers.group_stats(rows)
    assert st["n"] == 4 and st["n_used"] == 3
    assert st["eg1"]["n"] == 2 and st["eg1"]["mean"] == pytest.approx(17.5)
    assert st["pe1"]["median"] == pytest.approx(100 / 4.4, abs=1e-3)  # stats are rounded to 3 decimals


def test_universe_pages_through_every_sector_and_skips_non_common_shares():
    calls = []

    def screen(sector, min_cap, offset):
        calls.append((sector, offset))
        if sector != "Technology":
            return {"total": 0, "quotes": []}
        page = [{"symbol": f"T{offset + i}", "quoteType": "EQUITY"} for i in range(2)]
        if offset == 0:
            page += [{"symbol": "ABC-PA", "quoteType": "EQUITY"}, {"symbol": "XYZ-WT", "quoteType": "EQUITY"}]
        return {"total": 6, "quotes": page if offset < 6 else []}

    out = yahoo.fetch_universe(2e9, screen)
    assert [q["symbol"] for q in out] == ["T0", "T1", "T4", "T5"] and out[0]["sector"] == "Technology"
    assert len(calls) == len(yahoo.SECTORS) + 1
    with pytest.raises(FetchError):
        yahoo.fetch_universe(2e9, lambda s, m, o: {"total": 0, "quotes": []})


def test_trim_summary_reads_raw_values():
    raw = {
        "assetProfile": {"sector": "Technology", "industry": "Software", "country": "United States"},
        "price": {"currency": "USD", "quoteType": "EQUITY"},
        "earningsTrend": {
            "trend": [
                {"period": "0y", "endDate": "2027-01-31",
                 "earningsEstimate": {"avg": {"raw": 16.75, "fmt": "16.75"}, "yearAgoEps": {"raw": 12.52},
                                      "numberOfAnalysts": {"raw": 52}, "earningsCurrency": "USD"},
                 "revenueEstimate": {"avg": {"raw": 4.6e10}, "yearAgoRevenue": {"raw": 4.15e10}},
                 "epsTrend": {"90daysAgo": {"raw": 16.1}}},
                {"period": "+1y", "earningsEstimate": {"avg": {"raw": 16.02}}},
            ]
        },
        "calendarEvents": {"earnings": {"earningsDate": [1796241600], "isEarningsDateEstimate": True}},
    }  # fmt: skip
    s = yahoo.trim_summary(raw)
    assert s["0y"]["eps"] == 16.75 and s["0y"]["eps_year_ago"] == 12.52 and s["+1y"]["eps"] == 16.02
    assert s["0y"]["eps_90d_ago"] == 16.1 and s["industry"] == "Software" and s["earnings_date"] == 1796241600


def fake_screen(symbols):
    def screen(sector, min_cap, offset):
        if sector != "Technology" or offset:
            return {"total": len(symbols) if sector == "Technology" else 0, "quotes": []}
        return {"total": len(symbols), "quotes": [quote(s) for s in symbols]}

    return screen


def fake_summary_json(fail=()):
    def get_json(url, params):
        sym = url.rsplit("/", 1)[-1]
        if sym in fail:
            raise FetchError("429 Too Many Requests")
        return {"quoteSummary": {"result": [{
            "assetProfile": {"industry": "Software", "country": "United States"},
            "earningsTrend": {"trend": [
                {"period": "0y", "earningsEstimate": {"avg": 5.0, "yearAgoEps": 4.0, "numberOfAnalysts": 9,
                                                      "earningsCurrency": "USD"}},
                {"period": "+1y", "earningsEstimate": {"avg": 6.0}},
            ]},
        }]}}  # fmt: skip

    return get_json


def test_builder_budget_cache_and_fallback(tmp_path):
    cache = RawCache(tmp_path)
    syms = ["A", "B", "C", "D"]
    b = ScreenerBuilder(
        cache, params={"summary_budget": 3}, screen=fake_screen(syms), get_json=fake_summary_json(), now=NOW
    )
    data = b.build(TODAY)
    assert len(data["rows"]) == 4 and data["status"]["estimates"]["downloaded"] == 3
    flags = {r[0]: r[data["columns"].index("flags")] for r in data["rows"]}
    assert sum("no_profile" in f for f in flags.values()) == 1

    # next run: the universe download fails -> last good copy; the missing stock is fetched first
    def broken(*a):
        raise RuntimeError("Yahoo down")

    later = datetime(2026, 10, 22, 8, 0, tzinfo=UTC)
    b2 = ScreenerBuilder(
        cache, params={"summary_budget": 1}, screen=broken, get_json=fake_summary_json(), now=later
    )
    data2 = b2.build(TODAY)
    assert data2["status"]["universe"]["status"] == "failed" and len(data2["rows"]) == 4
    assert (
        data2["status"]["estimates"]["downloaded"] == 1
        and data2["status"]["estimates"]["with_estimates"] == 4
    )
    assert status_of(data2)["status"] == "degraded"


def test_builder_stops_after_repeated_failures(tmp_path):
    syms = [f"S{i}" for i in range(10)]
    b = ScreenerBuilder(
        RawCache(tmp_path),
        params={"summary_fail_stop": 3},
        screen=fake_screen(syms),
        get_json=fake_summary_json(fail=set(syms)),
        now=NOW,
    )
    data = b.build(TODAY)
    est = data["status"]["estimates"]
    assert est["failed"] == 3 and est["downloaded"] == 0 and "429" in est["error"]
    offline = ScreenerBuilder(RawCache(tmp_path / "empty"), offline=True).build(TODAY)
    assert offline["rows"] == [] and status_of(offline)["status"] == "failed"
