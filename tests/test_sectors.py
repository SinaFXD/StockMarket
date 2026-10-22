"""Sectors side by side: fundamentals per sector, rotation quadrants, cyclicals vs defensives, macro winds."""

import json

import pandas as pd
import pytest

from pipeline.config import SECTORS
from pipeline.sectors import build as sectors

P = dict(SECTORS)
DAYS = [d.date().isoformat() for d in pd.bdate_range("2025-06-02", periods=300)]


def row(t, sector="Technology", cls="boring", **kw):
    base = {"t": t, "name": t, "sector": sector, "industry": "Software", "cls": cls, "mcap": 1e9, "flags": [],
            "eg1": 10.0, "eg2": 12.0, "pe1": 20.0, "peg1": 2.0, "rg1": 5.0, "rv": 30.0, "r3m": 1.0,
            "eps1_rev90": 0.0, "vol_ok": True}  # fmt: skip
    return {**base, **kw}


def test_fundamentals_use_clean_stocks_and_count_revisions():
    rows = [
        row("A", eg1=10, eps1_rev90=5, cls="positive"),
        row("B", eg1=30, eps1_rev90=-3, cls="negative"),
        row("C", eg1=20, eps1_rev90=0.5),
        row("D", eg1=900, flags=["extreme_growth"], eps1_rev90=9),  # left out of medians, still counted
    ]
    f = sectors.fundamentals(rows, P)
    assert f["n"] == 4 and f["n_clean"] == 3 and f["eg1"] == 20 and f["mcap"] == 4e9
    assert f["rev_up"] == pytest.approx(33.3, abs=0.1) and f["rev_down"] == pytest.approx(33.3, abs=0.1)
    assert f["types"] == {"positive": 1, "negative": 1, "boring": 2}
    assert sectors.fundamentals([], P)["eg1"] is None and sectors.fundamentals([], P)["rev_up"] is None


def test_candidates_put_the_volatility_filter_first_then_size():
    rows = [
        row("BIG", cls="positive", mcap=9e9, vol_ok=False),
        row("MID", cls="positive", mcap=5e9),
        row("SMALL", cls="positive", mcap=1e9),
        row("SHORT", cls="post_growth", mcap=8e9),
    ]
    assert [c["t"] for c in sectors.candidates(rows, sectors.LONG, 5)] == ["MID", "SMALL", "BIG"]
    assert [c["t"] for c in sectors.candidates(rows, sectors.SHORT, 5)] == ["SHORT"]
    assert len(sectors.candidates(rows, sectors.LONG, 2)) == 2


def line(start_rs, end_rs, mid_rs=None):
    """A relative line whose 3-month strength is `end_rs` now and `start_rs` a month ago."""
    lb, mom = int(P["rs_days"]), int(P["rs_momentum_days"])
    n = lb + mom + 1
    rel = [1.0] * n
    rel[-1] = 1 + end_rs / 100  # vs rel[-lb-1] == 1
    rel[-mom - 1] = 1 + start_rs / 100  # vs rel[-lb-mom-1] == 1
    return rel


@pytest.mark.parametrize(
    ("then", "now", "quadrant"),
    [(2, 5, "leading"), (8, 5, "weakening"), (-2, -5, "lagging"), (-8, -5, "improving")],
)
def test_rotation_quadrants(then, now, quadrant):
    r = sectors.rotation(line(then, now), P)
    assert (
        r["quadrant"] == quadrant
        and r["rs"] == pytest.approx(now)
        and r["change"] == pytest.approx(now - then)
    )


def test_rotation_needs_enough_history():
    assert sectors.rotation([1.0] * 10, P) is None


def test_macro_wind_is_stock_weighted():
    themes = {"industries": [{"industry": "Software", "net": 2}, {"industry": "Banks", "net": -1},
                             {"industry": "Other", "net": None}]}  # fmt: skip
    rows = [row("A"), row("B"), row("C", industry="Banks"), row("D", industry="Other")]
    m = sectors.macro_wind(rows, themes)
    assert m["score"] == 1.0 and m["tailwinds"] == [["Software", 2]] and m["headwinds"] == [["Banks", -1]]
    assert (
        sectors.macro_wind(rows, None) is None
        and sectors.macro_wind([row("X", industry="Other")], themes) is None
    )


@pytest.mark.parametrize(
    ("bias", "spread", "market", "verdict"),
    [
        ("net_long", 5, "cyclical", "agree"),
        ("net_short", 5, "cyclical", "disagree"),
        ("net_short", -5, "defensive", "agree"),
        ("net_long", 1, "mixed", "mixed"),
        ("neutral", -5, "defensive", "mixed"),
        (None, 5, "cyclical", "no bias"),
    ],
)
def test_agreement(bias, spread, market, verdict):
    assert sectors.agreement(bias, spread, P) == {"market": market, "verdict": verdict}
    assert sectors.agreement(bias, None, P) is None


def write_series(site, sym, values):
    p = site / "series" / "yahoo" / f"{sym}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    obs = [[d, v, v] for d, v in zip(DAYS, values, strict=True)]
    p.write_text(json.dumps({"columns": ["date", "close", "adj_close"], "observations": obs}))


def test_build_from_published_files(tmp_path):
    site = tmp_path
    n = len(DAYS)
    write_series(site, "SPY", [100.0] * n)
    for name, etf in sectors.SECTOR_ETF.items():
        # cyclicals and sensitives rise 10% over the last 3 months, defensives stay flat
        up = sectors.GROUP_OF[name] != "defensive"
        write_series(
            site, etf, [100.0 * (1.1 if up and i >= n - 63 - 1 and i == n - 1 else 1.0) for i in range(n)]
        )
    stocks = {
        "as_of": "2026-03-01",
        "columns": list(row("A").keys()),
        "rows": [
            list(row("A", cls="positive").values()),
            list(row("B", sector="Utilities", cls="negative").values()),
        ],
    }
    (site / "screener").mkdir()
    (site / "screener" / "stocks.json").write_text(json.dumps(stocks))
    (site / "macro").mkdir()
    (site / "macro" / "latest.json").write_text(
        json.dumps({"bias": {"state": "net_long", "label": "Net long", "score": 2}})
    )
    out = sectors.build(site)
    by = {s["sector"]: s for s in out["sectors"]}
    assert len(by) == 11 and by["Technology"]["etf"] == "XLK" and by["Technology"]["group"] == "sensitive"
    assert by["Technology"]["price"]["rs3m"] == pytest.approx(10) and by["Utilities"]["price"]["rs3m"] == 0
    assert by["Technology"]["long"][0]["t"] == "A" and by["Utilities"]["short"][0]["t"] == "B"
    assert by["Technology"]["rotation"]["quadrant"] == "leading"
    assert len(by["Technology"]["relative_line"]) == P["spark_days"] and by["Technology"]["macro"] is None
    assert out["groups"]["spread_3m"] == pytest.approx(10) and out["groups"]["defensive_3m"] == 0
    assert out["agreement"] == {"market": "cyclical", "verdict": "agree"}
    assert out["prices_as_of"] == DAYS[-1] and out["as_of"] == "2026-03-01"


def test_build_without_data(tmp_path):
    out = sectors.build(tmp_path)
    assert len(out["sectors"]) == 11 and out["groups"] == {} and out["agreement"] is None
    assert out["sectors"][0]["price"]["rs3m"] is None and out["sectors"][0]["rotation"] is None
