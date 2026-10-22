"""Point-in-time ("as of") data access, bias aggregation, alerts and the Macro Desk build."""

import csv
import json
from datetime import date

import pandas as pd
from signal_helpers import TODAY, P, daily, frame, library, monthly

from pipeline.signals import build, data
from pipeline.signals.bias import PRICE_ALERT_PREFIX, alerts, combine, price_alert, what_changed

# ------------------------------------------------------------------ as of ------------------------------------

CPI_VINTAGES = [  # CPI July 2026 first printed 332.8 on 2026-08-12, revised to 332.9 on 2027-02-10
    ["2026-06-01", "2026-07-15", "9999-12-31", "331.0"],
    ["2026-07-01", "2026-08-12", "2027-02-09", "332.8"],
    ["2026-07-01", "2027-02-10", "9999-12-31", "332.9"],
    ["2026-08-01", "2026-09-11", "9999-12-31", "334.1"],
]


def test_vintages_give_the_series_as_published_that_day():
    lib = library(
        {"fred/CPIAUCSL": (monthly([331.0, 332.9, 334.1], last="2026-08"), "monthly")},
        today=date(2027, 3, 1),
        vintages={"fred/CPIAUCSL": CPI_VINTAGES},
    )
    s = lib.view(date(2026, 8, 20)).series("fred/CPIAUCSL")
    assert list(s.index.strftime("%Y-%m")) == ["2026-06", "2026-07"] and s.iloc[-1] == 332.8
    assert lib.view(date(2027, 2, 15)).series("fred/CPIAUCSL").loc["2026-07-01"] == 332.9
    assert lib.view(date(2027, 3, 1)).series("fred/CPIAUCSL").iloc[-1] == 334.1  # today: current data


def test_before_alfred_coverage_revised_data_is_used_and_flagged():
    lib = library(
        {"fred/CPIAUCSL": (monthly([300.0, 301.0, 302.0], last="2020-03"), "monthly")},
        vintages={"fred/CPIAUCSL": CPI_VINTAGES},
    )
    view = lib.view(date(2020, 5, 20))
    s = view.series("fred/CPIAUCSL")
    assert list(s.index.strftime("%Y-%m")) == ["2020-01", "2020-02", "2020-03"]  # 45-day publication lag
    assert "fred/CPIAUCSL" in view.revised
    assert len(lib.view(date(2020, 5, 10)).series("fred/CPIAUCSL")) == 2


def test_daily_prices_and_monthly_surveys_known_by_their_dates():
    lib = library(
        {
            "yahoo/GSPC": (daily([("2026-09-01", 100), ("2026-10-20", 110)]), "daily"),
            "umich/ICS": (monthly([50.0, 55.0], last="2026-09"), "monthly"),
        }
    )
    view = lib.view(date(2026, 9, 29))
    assert view.series("yahoo/GSPC").index[-1] == pd.Timestamp("2026-09-29")
    assert view.series("umich/ICS").index[-1] == pd.Timestamp("2026-08-01")  # September final not out yet
    assert lib.view(date(2026, 9, 30)).series("umich/ICS").index[-1] == pd.Timestamp("2026-09-01")


def test_manual_reports_are_known_from_their_release_date():
    df = frame({"pmi": [52.0, 53.0], "new_orders": [55.0, 54.0]}, last="2026-09")
    lib = library(manual={"ism_manufacturing": df})
    assert lib.view(date(2026, 9, 30)).manual("ism_manufacturing", "pmi").iloc[-1] == 52.0
    assert lib.view(date(2026, 10, 1)).manual("ism_manufacturing", "pmi").iloc[-1] == 53.0
    view = lib.view(date(2026, 11, 20))  # October report out on Nov 2 and still not entered
    assert "2026-10 report" in view.manual_stale("ism_manufacturing", "pmi")
    assert lib.view(date(2026, 11, 4)).manual_stale("ism_manufacturing", "pmi") is None  # grace period


def test_month_ends_stop_before_the_current_month():
    ends = data.month_ends("2026-07", date(2026, 10, 21))
    assert ends == [date(2026, 7, 31), date(2026, 8, 31), date(2026, 9, 30)]


# ------------------------------------------------------------------ bias -------------------------------------


def sig(i, block, score):
    return {"id": i, "name": i, "block": block, "score": score, "state": "x", "flags": []}


def test_blocks_are_averaged_then_the_bias_and_awaiting_signals_are_left_out():
    signals = [
        sig("a", "money_markets", 1),
        sig("b", "money_markets", 0),
        sig("c", "surveys", -1),
        sig("d", "surveys", None),
        sig("e", "prices_fx_equities", 1),
        sig("f", "international", None),
    ]
    b = combine(signals, 0.25)
    assert b["blocks"]["money_markets"]["score"] == 0.5 and b["blocks"]["surveys"]["score"] == -1
    assert b["blocks"]["international"]["score"] is None
    assert b["score"] == round((0.5 - 1 + 1) / 3, 3) and b["state"] == "neutral"
    assert (b["used"], b["total"]) == (4, 6)


def test_overrides_and_thresholds():
    signals = [sig("a", "money_markets", 0), sig("c", "surveys", 0)]
    assert combine(signals, 0.25, {"a": 1})["state"] == "net_long"
    assert combine(signals, 0.25, {"a": -1, "c": -1})["state"] == "net_short"
    assert combine([], 0.25)["state"] is None


def test_alerts_for_disagreement_m2_and_flags():
    signals = [sig("curve", "money_markets", 1), sig("m2", "money_markets", 1), sig("x", "surveys", -1)]
    signals[2]["flags"] = ["Potential lie: official NBS 50.4 > 50 while private RatingDog 49.0 < 50."]
    out = alerts(signals, combine(signals, 0.25), 0.25)
    assert any(a.startswith("Blocks disagree") for a in out)
    assert any("what does the Fed see" in a for a in out)
    assert any("Potential lie" in a for a in out)


def test_data_vs_prices_alert_only_when_bias_and_the_sp500_trend_disagree():
    assert price_alert("net_short", 1) == "data_weak_price_up"
    assert price_alert("net_long", -1) == "data_strong_price_down"
    assert price_alert("net_short", -1) is None and price_alert("neutral", 1) is None
    assert price_alert("net_long", None) is None  # S&P trend awaiting data: no alert
    weak = [sig("a", "money_markets", -1), sig("b", "surveys", -1), sig("sp500", "prices_fx_equities", 1)]
    bias = combine(weak, 0.25)
    assert bias["state"] == "net_short"  # (-1 - 1 + 1) / 3 blocks
    first = alerts(weak, bias, 0.25)[0]
    assert first.startswith(PRICE_ALERT_PREFIX) and "uptrend" in first
    calm = [sig("a", "money_markets", 1), sig("sp500", "prices_fx_equities", 1)]
    assert not any(a.startswith(PRICE_ALERT_PREFIX) for a in alerts(calm, combine(calm, 0.25), 0.25))


def test_what_changed_lists_score_moves():
    before = {
        "bias": {"score": 0.1, "state": "neutral", "label": "Neutral"},
        "signals": [sig("a", "surveys", 0)],
    }
    now = {
        "bias": {"score": 0.4, "state": "net_long", "label": "Net long"},
        "signals": [sig("a", "surveys", 1)],
    }
    changes = what_changed(now, before)
    assert [c["id"] for c in changes] == ["bias", "a"] and changes[1]["to"] == 1


# ------------------------------------------------------------------ build ------------------------------------


def test_build_writes_latest_history_snapshots_and_log(tmp_path):
    lib = library(
        {
            "fred/T10Y2Y": (daily([("2016-01-04", 1.0), ("2026-10-20", 1.5)]), "daily"),
            "yahoo/GSPC": (daily([("2016-01-04", 2000), ("2026-10-20", 7000)]), "daily"),
        }
    )
    latest = build.build(tmp_path, TODAY, lib, start="2026-01")
    assert latest["bias"]["used"] == 2 and len(latest["signals"]) == 19
    curve = next(s for s in latest["signals"] if s["id"] == "curve")
    assert curve["history"][0][0] == "2026-01" and curve["reason_en"]
    hist = json.loads((tmp_path / "macro" / "history.json").read_text())
    assert hist["months"][-1] == "2026-09" and len(hist["signals"]["curve"]) == 9
    snaps = json.loads((tmp_path / "macro" / "snapshots" / "2026.json").read_text())
    assert snaps[0]["as_of"] == "2026-01-31"
    build.build(tmp_path, TODAY, lib, start="2026-09")  # same day again: the log row is replaced, not doubled
    rows = list(csv.DictReader((tmp_path / "macro" / "log.csv").open()))
    assert [r["date"] for r in rows] == ["2026-10-21"] and rows[0]["curve"] == "0"  # slow rise = stable


def test_a_failing_rule_does_not_hide_the_others(monkeypatch):
    def boom(view, params):
        raise ZeroDivisionError("bad")

    boom.__module__ = "pipeline.signals.money_markets"
    monkeypatch.setattr(build, "RULES", [boom, *build.RULES[1:]])
    snap = build.snapshot(library().view(TODAY), P)
    assert snap["signals"][0]["status"] == "awaiting" and "internal error" in snap["signals"][0]["reason_en"]
