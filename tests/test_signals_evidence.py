"""Confirmers (shown, not scored) and the Evidence page arithmetic."""

import pandas as pd
import pytest
from signal_helpers import TODAY, daily, library, monthly

from pipeline.signals import confirmers, evidence


def test_confirmer_tones_and_disagreement_with_the_bias():
    lib = library(
        {
            "fred/PAYEMS": (monthly([1000, 1100, 1200, 1300]), "monthly"),  # +100k a month -> supportive
            "fred/UNRATE": (monthly([3.5, 3.7, 3.9, 4.2]), "monthly"),  # +0.7pp -> weak
            "fred/INDPRO": (monthly([100.0] * 12 + [97.0] * 2), "monthly"),  # -3% YoY -> weak
        }
    )
    c = confirmers.build_confirmers(lib.view(TODAY), {"state": "net_long"})
    tones = {i["id"]: i["tone"] for i in c["growth"]}
    assert tones == {"payrolls": 1, "unemployment": -1, "industrial_production": -1}
    assert c["summary"]["weak"] == 2 and "disagree" in c["summary"]["text"]
    assert not c["inflation"]  # no CPI loaded: nothing invented
    agree = confirmers.summary(c["growth"], {"state": "net_short"})
    assert "agree" in agree["text"] and "disagree" not in agree["text"]


def test_quarterly_gdp_is_annualised_and_claims_use_four_week_averages():
    gdp = pd.Series([100.0, 101.0], index=pd.to_datetime(["2026-01-01", "2026-04-01"]))
    weeks = pd.date_range("2026-04-04", periods=20, freq="W-SAT")
    claims = pd.Series([200_000.0] * 16 + [260_000.0] * 4, index=weeks)
    lib = library({"fred/GDPC1": (gdp, "quarterly"), "fred/ICSA": (claims, "weekly")})
    items = {i["id"]: i for i in confirmers.growth_items(lib.view(TODAY))}
    assert items["gdp"]["value"] == pytest.approx(4.06, abs=0.01) and items["gdp"]["tone"] == 1
    assert items["claims"]["tone"] == -1  # 4-week average up 30% vs 13 weeks earlier


def test_forward_return_uses_month_end_closes_and_stops_at_the_data():
    px = daily([("2026-01-02", 100.0), ("2026-10-20", 200.0)])
    jan = evidence.month_end("2026-01")
    r = evidence.forward_return(px, jan, 3)
    expected = (px[px.index <= "2026-04-30"].iloc[-1] / px[px.index <= "2026-01-31"].iloc[-1] - 1) * 100
    assert r == pytest.approx(expected)
    assert evidence.forward_return(px, evidence.month_end("2026-09"), 1) is None  # October not complete


def test_stats_and_overlap():
    s = evidence.stats([1.0, -2.0, 3.0, 4.0, None], months=3)
    assert s["n"] == 4 and s["n_independent"] == 1 and s["pct_up"] == 75.0 and s["mean"] == 1.5
    assert evidence.stats([], 1) == {"n": 0}


def history(states, revised=None):
    months = [f"2020-{m:02d}" for m in range(1, len(states) + 1)]
    score = {"net_long": 0.5, "neutral": 0.0, "net_short": -0.5}
    return {
        "months": months,
        "state": states,
        "bias": [score[s] for s in states],
        "revised": revised or [False] * len(states),
        "signals": {"curve": [1 if s == "net_long" else -1 if s == "net_short" else 0 for s in states]},
    }


def test_by_state_groups_returns_and_long_minus_short():
    px = daily([("2019-12-31", 100.0), ("2020-04-30", 140.0), ("2020-08-31", 100.0), ("2020-12-31", 120.0)])
    h = history(["net_long"] * 4 + ["net_short"] * 4 + ["neutral"] * 3, revised=[True] * 6 + [False] * 5)
    out = evidence.by_state(h, px)
    one = out["all"]["1m"]
    assert one["net_long"]["n"] == 4 and one["net_long"]["mean"] > 0  # Feb-May returns: mostly the rise
    assert one["net_short"]["n"] == 4 and one["net_short"]["mean"] < 0  # Jun-Sep returns: the fall
    assert one["long_minus_short"] == pytest.approx(one["net_long"]["mean"] - one["net_short"]["mean"])
    assert out["realtime"]["1m"]["all"]["n"] == 5  # revised months left out
    sig = evidence.by_signal(h, px, "1m")[0]
    assert sig["id"] == "curve" and sig["plus"]["n"] == 4 and sig["first_month"] == "2020-01"


def test_bands_merge_consecutive_months_and_skip_neutral():
    h = history(["net_long", "net_long", "neutral", "net_short"])
    assert evidence._bands(h) == [
        {"from": "2020-01-31", "to": "2020-03-31", "tone": "pos"},
        {"from": "2020-04-30", "to": "2020-05-31", "tone": "neg"},
    ]


def test_exposure_curve_needs_a_year_and_goes_short_on_net_short():
    px = daily([("2019-12-31", 100.0), ("2021-12-31", 200.0)])
    up_year = history(["net_short"] * 12)
    curve = evidence.exposure_curve(up_year, px)
    assert curve["bias_scaled"]["cagr"] < 0 < curve["buy_and_hold"]["cagr"]
    assert evidence.exposure_curve(history(["net_long"] * 6), px) is None
