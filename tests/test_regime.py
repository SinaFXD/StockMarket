"""Regime page: growth vs inflation, regime history, recession odds, Taylor rule, Treasury curve, returns by regime."""

import json
from datetime import date

import pandas as pd
import pytest
from signal_helpers import daily, library, monthly

from pipeline.config import REGIME
from pipeline.regime import build as regime

P = dict(REGIME)
TODAY = date(2026, 10, 21)


def index(rates: list[float], start: float = 100.0, last: str = "2026-09") -> pd.Series:
    """A monthly price index growing by the given annual rates (% per year), one rate per month."""
    vals, v = [], start
    for r in rates:
        v *= (1 + r / 100) ** (1 / 12)
        vals.append(v)
    return monthly(vals, last=last)


def test_growth_is_the_three_month_average():
    g = regime.growth(monthly([0.3, -0.6, 0.0, 0.9]), P)
    assert list(g.round(3)) == [-0.1, 0.1]


def test_inflation_momentum_is_zero_at_a_steady_rate_and_positive_when_it_speeds_up():
    steady = regime.inflation_momentum(index([2.5] * 30), P)
    assert steady.abs().max() == pytest.approx(0, abs=1e-9)
    faster = regime.inflation_momentum(index([2.0] * 24 + [4.0] * 6), P)
    assert faster.iloc[-1] == pytest.approx(4.0 - ((1.02**0.5) * (1.04**0.5) - 1) * 100, abs=1e-6)
    assert regime.inflation_momentum(index([4.0] * 24 + [2.0] * 6), P).iloc[-1] < 0


@pytest.mark.parametrize(
    ("g", "i", "name"),
    [(0.2, -0.3, "recovery"), (0.0, 0.0, "overheat"), (-0.5, 0.4, "stagflation"), (-0.1, -0.1, "reflation")],
)
def test_classify(g, i, name):
    assert regime.classify(g, i, P) == name


EASING = [5 - 0.05 * k for k in range(40)]  # inflation slowing every month: momentum always negative


def lib_with(cfnai, core, vintages=None, **extra):
    series = {"fred/CFNAI": (cfnai, "monthly"), "fred/PCEPILFE": (core, "monthly"), **extra}
    return library(series, vintages=vintages)


def test_reading_uses_the_latest_month_both_inputs_cover():
    cfnai = monthly([0.1] * 29, last="2026-08")
    core = index([2.0] * 24 + [4.0] * 6)  # through 2026-09
    r = regime.reading(lib_with(cfnai, core).view(TODAY), P)
    assert r["month"] == "2026-08" and r["regime"] == "overheat" and r["growth"] == pytest.approx(0.1)
    assert (
        "at or above its trend" in r["reason_en"] and "rising" in r["reason_en"] and r["borderline"] is False
    )


def test_history_flags_months_read_with_revised_data():
    cfnai = monthly([-0.4] * 40)
    core = index(EASING)
    # CFNAI vintages exist only from 2026-06: earlier month-ends fall back to revised values
    vint = [[d.strftime("%Y-%m-%d"), "2026-06-01", "9999-12-31", "-0.4"] for d in cfnai.index]
    core_vint = [[d.strftime("%Y-%m-%d"), "2000-01-01", "9999-12-31", str(v)] for d, v in core.items()]
    lib = lib_with(cfnai, core, vintages={"fred/CFNAI": vint, "fred/PCEPILFE": core_vint})
    hist = regime.history(lib, TODAY, {**P, "history_start": "2026-03"})
    assert [h["month"] for h in hist] == [
        "2026-03",
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    ]
    assert [h["revised"] for h in hist] == [True, True, True, False, False, False, False]
    assert {h["regime"] for h in hist} == {"reflation"}


def test_new_york_fed_probit_matches_its_published_number():
    # Prob_Rec.pdf: Sep 2026 spread 0.95509 -> 12.7587% for Sep 2027
    p = regime.normal_cdf(P["probit_alpha"] + P["probit_beta"] * 0.95509)
    assert p * 100 == pytest.approx(12.7587, abs=0.01)


def test_recession_odds_monthly_average_complete_months_and_nber_spans():
    spread = daily([("1969-12-01", 0.95509), ("2026-10-20", 0.95509)])
    usrec = monthly([0] * 10 + [1] * 3 + [0] * 5, last="2026-09")
    lib = library({"fred/T10Y3M": (spread, "daily"), "fred/USREC": (usrec, "monthly")})
    out = regime.recession(lib.view(TODAY), TODAY, P)
    assert out["latest"]["spread_month"] == "2026-09" and out["latest"]["for_month"] == "2027-09"
    assert out["latest"]["prob"] == pytest.approx(12.76, abs=0.01)
    assert out["series"][0][0] == "1983-01"  # first month used (1982-01) + 12
    assert out["recessions"] == [["2026-02", "2026-04", 12.76]]  # the highest forecast for a recession month


def test_taylor_rule():
    assert regime.taylor_rate(3.0, -1.0, P) == pytest.approx(2 + 3 + 0.5 - 0.5)
    core = index([3.0] * 60)
    gdp = pd.Series([99.0, 99.0], index=pd.to_datetime(["2026-01-01", "2026-04-01"]))
    pot = pd.Series([100.0, 100.0, 100.0], index=pd.to_datetime(["2026-01-01", "2026-04-01", "2026-07-01"]))
    ff = monthly([4.0] * 60)
    lib = library(
        {
            "fred/PCEPILFE": (core, "monthly"),
            "fred/GDPC1": (gdp, "quarterly"),
            "fred/GDPPOT": (pot, "quarterly"),
            "fred/FEDFUNDS": (ff, "monthly"),
        }
    )
    out = regime.taylor(lib.view(TODAY), {**P, "taylor_start": "2026-01"})
    last = out["latest"]
    assert (
        last["month"] == "2026-09" and last["gap"] == pytest.approx(-1.0) and last["gap_quarter"] == "2026-04"
    )
    assert last["taylor"] == pytest.approx(5.0, abs=0.01) and last["gap_vs_rule"] == pytest.approx(
        -1.0, abs=0.01
    )
    assert out["rows"][0][0] == "2026-01"


def test_curve_keeps_one_curve_per_week_and_the_latest_day():
    series = {
        f"fred/{sid}": (daily([("2025-01-01", y), ("2026-10-20", y)]), "daily") for _, sid, y in regime.CURVE
    }
    series["fred/DGS30"] = (
        daily([("2025-01-01", 4.0), ("2026-10-19", 4.0)], end="2026-10-19"),
        "daily",
    )  # a day behind
    out = regime.curve(library(series).view(TODAY), TODAY, {**P, "curve_years": 1})
    assert out["labels"][0] == "1M" and out["labels"][-1] == "30Y" and len(out["years"]) == 11
    assert out["dates"][-1] == "2026-10-20" and out["yields"][-1][-1] is None
    assert out["yields"][-1][8] == pytest.approx(10)  # the 10y value is its maturity in years here
    assert all(d1 > d0 for d0, d1 in zip(out["dates"], out["dates"][1:], strict=False))
    assert 50 <= len(out["dates"]) <= 54


def test_returns_by_regime_and_the_real_time_view():
    months = pd.date_range("2020-01-31", periods=30, freq="ME")
    hist = [
        {"month": m.strftime("%Y-%m"), "regime": "recovery" if i % 2 else "reflation", "revised": i < 10}
        for i, m in enumerate(months)
    ]
    days = pd.bdate_range("2020-01-01", "2023-06-30")
    up = pd.Series([100 * 1.0005**k for k in range(len(days))], index=days)
    flat = pd.Series(100.0, index=days)
    out = regime.by_regime(hist, up, P)
    assert (
        out["first"] == "2020-01" and out["all"]["recovery"]["n"] == 15 and out["all"]["recovery"]["mean"] > 0
    )
    assert out["all"]["any"]["n"] == 30 and out["realtime"]["any"]["n"] == 20
    assert out["all"]["overheat"] == {"n": 0}
    excess = regime.by_regime(hist, flat, P, benchmark=up)
    assert excess["all"]["reflation"]["mean"] < 0 and excess["all"]["any"]["pct_up"] == 0


def write_prices(site, sym, days, values):
    p = site / "series" / "yahoo" / f"{sym}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    obs = [[d.strftime("%Y-%m-%d"), v, v] for d, v in zip(days, values, strict=True)]
    p.write_text(json.dumps({"columns": ["date", "close", "adj_close"], "observations": obs}))


def test_build_writes_every_part(tmp_path):
    cfnai = monthly([0.2] * 40)
    core = index(EASING)
    spread = daily([("2023-01-02", 1.0), ("2026-10-20", 1.0)])
    lib = lib_with(
        cfnai, core, **{"fred/T10Y3M": (spread, "daily"), "fred/USREC": (monthly([0] * 40), "monthly")}
    )
    days = pd.bdate_range("2023-01-02", "2026-10-20")
    write_prices(tmp_path, "SPY", days, [100 * 1.0004**k for k in range(len(days))])
    write_prices(tmp_path, "XLK", days, [100 * 1.0006**k for k in range(len(days))])
    write_prices(tmp_path, "GLD", days, [100.0] * len(days))
    out = regime.build(tmp_path, TODAY, lib=lib, p={"history_start": "2025-01"})
    assert out["now"]["regime"] == "recovery" and len(out["trail"]) == P["trail_months"]
    assert out["history"][0][:2] == ["2025-01", "recovery"] and out["counts"]["recovery"] == len(
        out["history"]
    )
    assert [s["id"] for s in out["sectors"]] == ["XLK"] and out["sectors"][0]["all"]["recovery"]["mean"] > 0
    assert [a["id"] for a in out["assets"]] == ["SPY", "GLD"] and out["assets"][1]["all"]["recovery"][
        "mean"
    ] == 0
    assert out["recession"]["latest"]["prob"] > 0 and out["taylor"] is None and out["curve"] is None
    assert regime.status_of(out)["regime"] == "Recovery"


def test_level_check_counts_hot_and_cold_levels():
    core = index([3.0] * 30)  # 3% inflation: 1 pp above target -> hot
    un = monthly([4.0] * 6)  # 0.4 below the natural rate -> hot (tight)
    nat = pd.Series([4.4, 4.4], index=pd.to_datetime(["2026-04-01", "2026-07-01"]))
    lib = library(
        {"fred/PCEPILFE": (core, "monthly"), "fred/UNRATE": (un, "monthly"), "fred/NROU": (nat, "quarterly")}
    )
    tay = {
        "latest": {
            "gap": 0.2,
            "gap_quarter": "2026-04",
            "fed_funds": 3.75,
            "taylor": 6.21,
            "gap_vs_rule": -2.46,
        }
    }
    out = regime.levels(lib.view(TODAY), P, tay)
    states = {i["id"]: i["state"] for i in out["items"]}
    assert states == {"inflation": "hot", "output_gap": "neutral", "unemployment": "hot"}
    assert out["verdict"] == "hot" and out["policy"]["state"] == "loose"
    un_item = next(i for i in out["items"] if i["id"] == "unemployment")
    assert un_item["natural"] == 4.4 and un_item["vs"] == pytest.approx(-0.4)
    cold = regime.levels(library({"fred/PCEPILFE": (index([1.0] * 30), "monthly")}).view(TODAY), P, None)
    assert (
        cold["verdict"] == "balanced" and cold["cold"] == 1 and cold["policy"] is None
    )  # one cold item is not enough
    assert regime.levels(library({}).view(TODAY), P, None) is None


def test_cpi_check_warns_when_the_newer_cpi_disagrees():
    now = {"month": "2026-08", "growth": 0.01, "inflation": -0.26, "regime": "recovery"}
    hotter = index([2.0] * 24 + [4.0] * 6)  # core CPI speeding up, through 2026-09
    out = regime.cpi_check(library({"fred/CPILFESL": (hotter, "monthly")}).view(TODAY), P, now)
    assert out["month"] == "2026-09" and out["newer"] and out["rising"] and not out["agrees"]
    assert out["regime"] == "overheat"
    calmer = regime.cpi_check(library({"fred/CPILFESL": (index(EASING), "monthly")}).view(TODAY), P, now)
    assert calmer["agrees"] and calmer["regime"] == "recovery"
    assert regime.cpi_check(library({}).view(TODAY), P, now) is None
