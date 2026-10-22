"""Every first-reading rule from docs/02, branch by branch, on hand-made data."""

from datetime import date

import pandas as pd
import pytest
from signal_helpers import TODAY, P, daily, frame, library, monthly, noisy

from pipeline.signals import international, money_markets, prices, surveys

# ---------------------------------------------------------------- money markets ------------------------------


@pytest.mark.parametrize(
    "then, now, score, state",
    [
        (0.2, -0.3, -1, "Inverted"),
        (0.6, 0.3, -1, "Flat & flattening"),
        (0.0, 0.4, 1, "Flat & steepening"),
        (0.4, 0.42, 0, "Flat"),
        (0.8, 1.2, 1, "Normal & steepening"),
        (1.0, 1.05, 0, "Normal"),
    ],
)
def test_curve(then, now, score, state):
    lib = library(
        {"fred/T10Y2Y": (daily([("2016-01-04", 1.0), ("2026-07-20", then), ("2026-10-20", now)]), "daily")}
    )
    sig = money_markets.curve(lib.view(TODAY), P)
    assert (sig.score, sig.state) == (score, state)
    assert f"{now:+.2f}pp" in sig.reason


def test_curve_flags_a_short_end_inversion_and_waits_for_stale_data():
    lib = library(
        {
            "fred/T10Y2Y": (daily([("2026-01-02", 0.3), ("2026-10-20", 0.3)]), "daily"),
            "fred/T10Y3M": (daily([("2026-01-02", 0.1), ("2026-10-20", -0.2)]), "daily"),
        }
    )
    assert "Short end inverted" in money_markets.curve(lib.view(TODAY), P).flags[0]
    stale = library(
        {"fred/T10Y2Y": (daily([("2026-01-02", 0.3), ("2026-08-03", 0.3)], end="2026-08-03"), "daily")}
    )
    sig = money_markets.curve(stale.view(TODAY), P)
    assert sig.score is None and sig.status == "awaiting" and "days old" in sig.reason


def _cpi(yoy_path: list[float], start: float = 100.0) -> pd.Series:
    """Monthly CPI index whose YoY follows ``yoy_path`` (one value per month, after a flat first year)."""
    values = [start] * 12
    for g in yoy_path:
        values.append(values[-12] * (1 + g / 100))
    return monthly(values)


@pytest.mark.parametrize(
    "yield_path, infl_now, score",
    [
        ([("2016-01-04", 5.0), ("2026-06-01", 5.0), ("2026-10-20", 1.0)], 3.0, 1),  # real rate at a 10y low
        ([("2016-01-04", 1.0), ("2026-06-01", 1.0), ("2026-10-20", 6.0)], 2.0, -1),  # high and rising
        ([("2016-01-04", 3.0), ("2026-10-20", 3.0)], 2.0, 0),
    ],
)
def test_real_rate(yield_path, infl_now, score):
    lib = library(
        {
            "fred/DGS10": (daily(yield_path), "daily"),
            "fred/CPIAUCSL": (_cpi([2.0] * 140 + [infl_now] * 2), "monthly"),
        }
    )
    sig = money_markets.real_rate(lib.view(TODAY), P)
    assert sig.score == score
    assert "CPI YoY" in sig.reason


def _spread(level: float, jump: float, seed: int) -> pd.Series:
    base = daily([("2022-01-03", level), ("2026-07-20", level)])
    noise = pd.Series(noisy(len(base), 0, 0.02, seed), index=base.index)
    s = base + noise
    s[s.index > "2026-07-20"] += [
        jump * i / (s.index > "2026-07-20").sum() for i in range(1, (s.index > "2026-07-20").sum() + 1)
    ]
    return s


@pytest.mark.parametrize(
    "jumps, score, state",
    [
        ((3.0, 0.0, 0.0), -1, "Junk widening first"),
        ((3.0, 0.5, 0.0), -1, "Widening"),
        ((-3.0, -0.5, -0.3), 1, "Tightening"),
        ((0.0, 0.0, 0.0), 0, "Stable"),
    ],
)
def test_credit(jumps, score, state):
    keys = ["fred/BAMLH0A3HYC", "fred/BAMLC0A4CBBB", "fred/BAMLC0A2CAA"]
    lib = library(
        {k: (_spread(5.0, j, i), "daily") for i, (k, j) in enumerate(zip(keys, jumps, strict=True))}
    )
    sig = money_markets.credit(lib.view(TODAY), P)
    assert (sig.score, sig.state) == (score, state)


def test_credit_falls_back_to_moodys_long_history():
    lib = library({"fred/BAA10Y": (_spread(2.0, 1.5, 7), "daily")})
    sig = money_markets.credit(lib.view(TODAY), P)
    assert sig.score == -1 and "Baa-10y" in sig.flags[0]


def _m2(last_growth: float, trend: float = 0.5) -> pd.Series:
    growth = noisy(800, trend, 0.3, 3) + [last_growth]
    values = [1000.0]
    for g in growth:
        values.append(values[-1] * (1 + g / 100))
    return monthly(values, last="2026-08")


@pytest.mark.parametrize("last, trend, score", [(3.0, 0.5, 1), (-0.5, -0.3, -1), (0.5, 0.5, 0)])
def test_m2(last, trend, score):
    lib = library({"fred/M2SL": (_m2(last, trend), "monthly")})
    assert money_markets.m2(lib.view(TODAY), P).score == score


def test_vix_uses_the_fresher_source():
    calm = daily([("2016-01-04", 20), ("2026-10-20", 12)])
    stressed = daily([("2016-01-04", 15), ("2026-07-20", 15), ("2026-10-20", 45)])
    lib = library({"fred/VIXCLS": (calm[:-5], "daily"), "yahoo/VIX": (stressed, "daily")})
    sig = money_markets.vix(lib.view(TODAY), P)
    assert sig.sources == ["yahoo/VIX"] and sig.score == -1
    lib = library({"fred/VIXCLS": (calm, "daily")})
    assert money_markets.vix(lib.view(TODAY), P).score == 1


# ---------------------------------------------------------------- surveys -------------------------------------


@pytest.mark.parametrize("pmi, orders, score", [(52.0, 53.0, 1), (47.0, 48.0, -1), (49.0, 52.0, 0)])
def test_ism_manufacturing(pmi, orders, score):
    df = frame({"pmi": [50.0] * 5 + [pmi], "new_orders": [50.0] * 5 + [orders], "inventories": [47.0] * 6})
    sig = surveys.ism_manufacturing(library(manual={"ism_manufacturing": df}).view(TODAY), P)
    assert sig.score == score
    assert sig.metrics["pmi_streak"]["months"] >= 1


def test_ism_manufacturing_flags_and_awaiting():
    df = frame({"pmi": [59.0, 59.5], "new_orders": [60.0, 61.0], "inventories": [50.0, 51.0]})
    sig = surveys.ism_manufacturing(library(manual={"ism_manufacturing": df}).view(TODAY), P)
    assert any("peak" in f for f in sig.flags) and any("orders are leading" in f for f in sig.flags)
    old = frame({"pmi": [52.0], "new_orders": [53.0]}, last="2026-07")
    sig = surveys.ism_manufacturing(library(manual={"ism_manufacturing": old}).view(TODAY), P)
    assert sig.score is None and "2026-08 report" in sig.reason


@pytest.mark.parametrize(
    "pmi, ba, no, score",
    [(54.0, 56.0, 55.0, 1), (48.0, 51.0, 51.0, -1), (51.0, 49.0, 48.0, -1), (51.0, 52.0, 49.0, 0)],
)
def test_ism_services(pmi, ba, no, score):
    df = frame({"pmi": [pmi], "business_activity": [ba], "new_orders": [no], "backlog": [50.5]})
    assert surveys.ism_services(library(manual={"ism_services": df}).view(TODAY), P).score == score


def _umich(ics: list[float], ice: list[float]) -> dict:
    return {
        "umich/ICS": (monthly(ics), "monthly"),
        "umich/ICE": (monthly(ice), "monthly"),
        "umich/ICC": (monthly(ics), "monthly"),
    }


@pytest.mark.parametrize(
    "ics, ice, score, state",
    [
        ([90, 90, 90, 88], [90, 90, 90, 78], -1, "Expectations falling"),
        ([68, 66, 65, 64], [60, 60, 60, 61], -1, "Pessimistic"),
        ([82, 83, 84, 86], [80, 80, 81, 82], 1, "Optimistic"),
        ([82, 83, 84, 76], [80, 80, 81, 79], 0, "Balanced"),
    ],
)
def test_umich(ics, ice, score, state):
    sig = surveys.umich(library(_umich(ics, ice)).view(TODAY), P)
    assert (sig.score, sig.state) == (score, state)


def _permits(growth_now: float) -> pd.Series:
    vals = [1400.0] * 24
    for i in range(24):
        vals.append(vals[-12] * (1 + growth_now / 100 * (i + 1) / 24))
    return monthly(vals)


@pytest.mark.parametrize("growth, score", [(10.0, 1), (-15.0, -1)])
def test_permits(growth, score):
    lib = library({"fred/PERMIT": (_permits(growth), "monthly")})
    assert surveys.permits(lib.view(TODAY), P).score == score


def _nfib(opt: list[float], lead: list[float]) -> dict:
    cols = {"optimism_index": opt}
    for c in surveys.NFIB_LEADING:
        cols[c] = lead
    return {"nfib_sbet": frame(cols)}


@pytest.mark.parametrize(
    "opt, lead, score, state",
    [
        ([101] * 8, [10, 10, 10, 10, 10, 12, 14, 16], 1, "Strong"),
        ([96] * 7 + [94.5], [10] * 8, -1, "Weak"),
        ([98] * 8, [10, 10, 10, 10, 10, 9, 8, 7], -1, "Leading index falling"),
        ([98] * 8, [10] * 8, 0, "Neutral"),
    ],
)
def test_nfib(opt, lead, score, state):
    sig = surveys.nfib(library(manual=_nfib(opt, lead)).view(TODAY), P)
    assert (sig.score, sig.state) == (score, state)


# ---------------------------------------------------------------- prices --------------------------------------


@pytest.mark.parametrize("start, end, score", [(100, 112, 1), (100, 88, -1), (100, 102, 0)])
def test_commodities_and_dollar(start, end, score):
    s = daily([("2025-01-02", start), ("2025-10-20", start), ("2026-10-20", end)])
    lib = library({"fred/DCOILBRENTEU": (s, "daily"), "fred/DTWEXBGS": (s, "daily")})
    assert prices.brent(lib.view(TODAY), P).score == score
    assert prices.dollar(lib.view(TODAY), P).score == -score  # a strong dollar is a headwind


def test_monthly_commodity_yoy():
    lib = library({"fred/WPU081": (monthly([100.0] * 12 + [110.0]), "monthly")})
    sig = prices.lumber(lib.view(TODAY), P)
    assert sig.score == 1 and sig.metrics["yoy_pct"] == pytest.approx(10.0)


@pytest.mark.parametrize(
    "path, score",
    [
        ([("2025-01-02", 100), ("2026-10-20", 130)], 1),
        ([("2025-01-02", 130), ("2026-10-20", 100)], -1),
        (
            [("2025-01-02", 100), ("2026-04-01", 140), ("2026-07-20", 150), ("2026-10-20", 145)],
            0,
        ),  # above, falling
    ],
)
def test_sp500_trend(path, score):
    lib = library({"yahoo/GSPC": (daily(path), "daily")})
    assert prices.sp500(lib.view(TODAY), P).score == score


# ---------------------------------------------------------------- international -------------------------------


@pytest.mark.parametrize(
    "vals, score", [([98, 99, 100, 102], 1), ([99, 98, 97, 95], -1), ([96, 97, 98, 99], 0)]
)
def test_esi(vals, score):
    lib = library({"eurostat/ESI_EA": (monthly(vals), "monthly")})
    assert international.esi(lib.view(TODAY), P).score == score


@pytest.mark.parametrize(
    "rd, score", [([49, 50, 50, 51], 1), ([51, 50, 49, 48], -1), ([51, 50, 49.5, 50.5], 0)]
)
def test_china(rd, score):
    df = frame({"ratingdog_manufacturing": rd, "nbs_manufacturing": [50.2] * 4})
    sig = international.china(library(manual={"china_pmi": df}).view(TODAY), P)
    assert sig.score == score
    assert ("Potential lie" in " ".join(sig.flags)) == (rd[-1] < 50)


def test_awaiting_data_when_nothing_is_loaded():
    view = library().view(date(2026, 10, 21))
    for rule in (money_markets.curve, surveys.nfib, prices.copper, international.china):
        assert rule(view, P).status == "awaiting"
