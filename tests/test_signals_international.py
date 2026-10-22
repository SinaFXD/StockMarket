"""International money markets (US template applied to Japan, UK, Germany, Italy) and the Global page."""

from datetime import date

import pytest
from signal_helpers import TODAY, P, daily, library, monthly

from pipeline.signals import global_view, international

N = 120  # ten years of monthly data


def country(cc: str, y10: float, rate: float, cpi_hist: float, cpi_now: float, rate_now: float | None = None):
    rate_now = rate if rate_now is None else rate_now
    return {
        f"oecd/Y10_{cc}": (monthly([y10] * N), "monthly"),
        f"oecd/RATE_{cc}": (monthly([rate] * (N - 3) + [rate_now] * 3), "monthly"),
        f"oecd/CPI_{cc}": (monthly([cpi_hist] * (N - 3) + [cpi_now] * 3), "monthly"),
    }


SUPPORTIVE = dict(y10=3, rate=2, cpi_hist=1, cpi_now=3)  # normal curve, real rate at a 10-year low -> +1
STRESSED = dict(y10=3, rate=2, cpi_hist=1, cpi_now=1, rate_now=4)  # inverted curve, high real rate -> -1
HIGH_AND_RISING = dict(y10=3, rate=2, cpi_hist=3, cpi_now=1)  # real rate jumps to the top of its history


def test_country_reading_uses_the_us_template():
    v = library(country("JP", **SUPPORTIVE)).view(TODAY)
    jp = international.country_rates(v, P, "JP")
    assert jp.status == "ok" and jp.score == 1
    assert jp.curve["state"] == "Normal" and jp.real["state"] == "Low vs history"
    assert jp.real["value"] == pytest.approx(0.0)
    de = international.country_rates(library(country("DE", **HIGH_AND_RISING)).view(TODAY), P, "DE")
    assert de.real["state"] == "High & rising" and de.score == -1


@pytest.mark.parametrize(
    "readings, score",
    [
        ([SUPPORTIVE] * 4, 1),
        ([STRESSED] * 4, -1),
        ([SUPPORTIVE, SUPPORTIVE, STRESSED, STRESSED], 0),
        ([SUPPORTIVE, SUPPORTIVE, SUPPORTIVE, STRESSED], 1),
    ],
)
def test_intl_money_markets_nets_the_countries(readings, score):
    series = {}
    for cc, r in zip(international.SCORED, readings, strict=True):
        series.update(country(cc, **r))
    sig = international.intl_money_markets(library(series).view(TODAY), P)
    assert sig.score == score
    if readings[-1] is STRESSED:
        assert any("Italy curve inverted" in f for f in sig.flags)


def test_intl_money_markets_needs_three_countries_and_ignores_china():
    series = {**country("JP", **SUPPORTIVE), **country("GB", **SUPPORTIVE), **country("CN", **STRESSED)}
    sig = international.intl_money_markets(library(series).view(TODAY), P)
    assert sig.status == "awaiting" and "Germany" in sig.reason


def test_oecd_monthly_data_is_known_45_days_after_the_month():
    lib = library(country("JP", **SUPPORTIVE))
    s = lib.view(date(2026, 10, 1)).series("oecd/Y10_JP")
    assert s.index[-1].strftime("%Y-%m") == "2026-07"
    assert not lib.view(date(2026, 10, 1)).revised  # OECD rates and CPI are not flagged as revised


def regions(r3m: list[float]) -> list[dict]:
    names = ["United States", "Europe", "Japan", "China"]
    return [{"name": n, "usd": {"r3m": x, "r12m": x}} for n, x in zip(names, r3m, strict=True)]


def test_dispersion_tells_global_from_local_moves():
    up = global_view.dispersion(regions([3.0, 1.0, 2.0, 0.5]))
    assert up["up"] == 4 and "global move" in up["reading"] and up["leader"] == "United States"
    mixed = global_view.dispersion(regions([3.0, -1.0, 2.0, -6.0]))
    assert mixed["laggard"] == "China" and mixed["spread"] == pytest.approx(9.0)
    assert "Dispersion" in mixed["reading"]
    assert "Not enough" in global_view.dispersion(regions([1.0, None, None, 2.0]))["reading"]


def test_global_page_data_with_and_without_prices():
    px = daily([("2025-01-02", 100.0), ("2026-10-20", 120.0)])
    flat = daily([("2025-01-02", 100.0), ("2026-10-20", 100.0)])
    series = {
        "yahoo/GSPC": (px, "daily"),
        "yahoo/SPY": (px, "daily"),
        "yahoo/VGK": (flat, "daily"),
        **country("JP", **SUPPORTIVE),
    }
    d = global_view.build_global(library(series).view(TODAY), P)
    us, eu = d["regions"][0], d["regions"][1]
    assert us["usd"]["r12m"] > 0 and eu["vs_us"]["12m"] < 0 and d["regions"][3]["usd"] is None
    jp = next(c for c in d["countries"] if c["code"] == "JP")
    assert jp["status"] == "ok" and jp["scored"] and jp["score"] == 1
    cn = next(c for c in d["countries"] if c["code"] == "CN")
    assert cn["status"] == "awaiting" and not cn["scored"]
    rel = next(p for p in d["panels"] if p["title"].startswith("Relative strength"))
    assert rel["rebase"] and rel["series"][0]["name"] == "Europe vs US"
    empty = global_view.build_global(library().view(TODAY), P)  # no data: no crash
    assert all(r["local"] is None for r in empty["regions"])
