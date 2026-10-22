"""Outlier classification against the sector, and the volatility filter."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from pipeline.config import SCREENER
from pipeline.screener import outliers, volatility

P = dict(SCREENER)


def stock(t, eg1, eg2, pe1=20.0, eps0=1.0, sector="Tech", flags=None, rg=(5.0, 5.0), rev=None):
    eps1 = None if eg1 is None else eps0 * (1 + eg1 / 100)
    eps2 = None if eg2 is None or eps1 is None else eps1 * (1 + eg2 / 100)
    return {"t": t, "sector": sector, "eg1": eg1, "eg2": eg2, "pe1": pe1, "eps0": eps0, "eps1": eps1, "eps2": eps2,
            "flags": flags or [], "rg1": rg[0], "rg2": rg[1], "eps1_rev90": rev}  # fmt: skip


def sector(extra):
    """20 ordinary peers growing 5-24% a year, plus the stocks under test."""
    peers = [stock(f"P{i}", 5 + i, 5 + i, pe1=15 + i) for i in range(20)]
    return peers + extra


def classify(extra):
    rows = sector(extra)
    outliers.classify(rows, P)
    return {r["t"]: r for r in rows}


def test_positive_and_negative_outliers_need_both_years():
    r = classify(
        [
            stock("UP", 60, 50, rev=8),
            stock("UP1", 60, 10),  # one strong year only
            stock("DOWN", -30, -20, pe1=12, rg=(-3, -2)),
            stock("DOWN1", -30, 20),  # falls then recovers
        ]
    )
    assert r["UP"]["cls"] == "positive" and "consecutive" in r["UP"]["why"]
    assert "EPS1 estimate raised 8% in 90 days" in r["UP"]["notes"]
    assert r["UP1"]["cls"] != "positive"
    assert r["DOWN"]["cls"] == "negative" and "sales falling both years" in r["DOWN"]["notes"]
    assert r["DOWN1"]["cls"] == "turnaround"


def test_post_growth_value_trap_loss_and_profit_turning_to_loss():
    r = classify(
        [
            stock("POST", 80, -40),
            stock("TRAP", 2, -5, pe1=8),
            stock("BACK", None, None, eps0=-1.0),
            stock("LOSS", None, None, eps0=-1.0),
            stock("TURN", 10, None),
        ]
    )
    assert r["POST"]["cls"] == "post_growth"
    assert r["TRAP"]["cls"] == "value_trap" and "cheapest quarter" in r["TRAP"]["why"]
    # loss -> profit: EPS0 < 0, EPS1 > 0
    back = stock("B2", None, None, eps0=-1.0)
    back.update(eps1=0.5, eps2=0.8)
    loss = stock("L2", None, None, eps0=-1.0)
    loss.update(eps1=-0.5, eps2=-0.2)
    drop = stock("D2", 10, None)
    drop.update(eps1=1.1, eps2=-0.3)
    r2 = classify([back, loss, drop])
    assert r2["B2"]["cls"] == "turnaround" and "Back to profit" in r2["B2"]["why"]
    assert r2["L2"]["cls"] == "loss"
    assert r2["D2"]["cls"] == "negative" and "losses" in r2["D2"]["why"]


def test_percentiles_use_clean_sector_peers_and_flagged_rows_are_not_classified():
    r = classify([stock("ADR", 90, 90, flags=["currency"]), stock("MID", 14, 14)])
    assert r["ADR"]["cls"] == "na"
    assert r["MID"]["cls"] == "boring" and 25 < r["MID"]["eg1_pct"] < 75
    assert r["P19"]["eg1_pct"] == pytest.approx(100.0)
    assert r["MID"]["pe_prem"] is not None


def test_small_sector_falls_back_to_the_universe():
    rows = sector([stock("LONE", 50, 50, sector="Tiny")])
    medians = outliers.classify(rows, P)
    assert medians["Tiny"]["peers"] == 21  # one stock: compared with the whole clean universe (20 + LONE)
    assert medians["Tech"]["peers"] == 20  # enough peers: its own sector


def test_black_scholes_round_trip_and_atm_iv():
    for call in (True, False):
        price = volatility.bs_price(100, 105, 0.25, 0.04, 0.3, call)
        assert volatility.implied_vol(price, 100, 105, 0.25, 0.04, call) == pytest.approx(0.3, abs=1e-4)
    assert volatility.implied_vol(0.01, 100, 50, 0.25, 0.04, True) is None  # below intrinsic value
    calls = [{"strike": k, "bid": 0, "ask": 0, "lastPrice": volatility.bs_price(100, k, 0.12, 0.04, 0.4, True)}
             for k in (90, 100, 110)]  # fmt: skip
    puts = [{"strike": k, "bid": 0, "ask": 0, "lastPrice": volatility.bs_price(100, k, 0.12, 0.04, 0.4, False)}
            for k in (95, 100, 105)]  # fmt: skip
    assert volatility.atm_iv(100, calls, puts, 0.12, 0.04) == pytest.approx(40.0, abs=0.1)


def test_realised_volatility_and_atr():
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, 130)))
    frame = pd.DataFrame({"Close": close, "High": close * 1.01, "Low": close * 0.99})
    out = volatility.realised(frame, 63, 14)
    assert out["rv"] == pytest.approx(0.02 * np.sqrt(252) * 100, rel=0.25)
    assert 1.5 < out["atr"] < 4.5
    assert volatility.realised(frame.iloc[:10], 63, 14) == {"rv": None, "atr": None}


class FakeTicker:
    def __init__(self, expiries, price=5.0):
        self.options = expiries
        self.price = price

    def option_chain(self, expiry):
        df = pd.DataFrame({"strike": [95.0, 100.0, 105.0], "bid": 0.0, "ask": 0.0, "lastPrice": self.price})

        class Chain:
            calls = df
            puts = df

        return Chain()


def test_fetch_iv_picks_the_expiry_nearest_45_days_and_treats_empty_lists_as_failures():
    today = date(2026, 10, 22)
    t = FakeTicker(["2026-10-23", "2026-11-27", "2026-12-18", "2027-01-15"])
    res = volatility.fetch_iv("X", 100.0, today, 45, 0.04, t)
    assert res["expiry"] == "2026-11-27" and res["iv"] is not None  # 36 days is closer to 45 than 57
    with pytest.raises(Exception, match="no option expiries"):
        volatility.fetch_iv("X", 100.0, today, 45, 0.04, FakeTicker([]))
