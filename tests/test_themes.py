"""Macro-driven ideas (lessons 34-35): the macro -> industry map, ISM industry lists, the ideas list, international
listings and the China check."""

import json

import pytest

from pipeline.config import THEMES
from pipeline.signals import international, money_markets, prices, surveys
from pipeline.themes import build as tb

P = dict(THEMES)
MAP = {
    "signals": [
        {"id": "oil", "signal": "brent", "label": "Oil", "why": "Oil.", "industries": {"Oil & Gas E&P": 1, "Airlines": -1}},
        {"id": "consumer", "signal": "umich", "label": "Consumer", "why": "Spending.", "industries": {"Restaurants": 1}},
    ],
    "ism": {
        "manufacturing": {"Petroleum & Coal Products": ["Oil & Gas Refining & Marketing"], "Machinery": ["Specialty Industrial Machinery"]},
        "services": {"Transportation & Warehousing": ["Airlines"], "Mining": ["Oil & Gas E&P"]},
    },
    "regions": {"China": ["China", "Hong Kong"], "Europe": ["Germany"]},
}  # fmt: skip


def test_the_real_map_loads_and_names_live_signals():
    m = tb.load_map()
    live = {f.__name__ for mod in (money_markets, surveys, prices, international) for f in mod.SIGNALS}
    assert {t["signal"] for t in m["signals"]} <= live
    assert all(isinstance(v, list) for rep in m["ism"].values() for v in rep.values())
    assert len(m["ism"]["manufacturing"]) == 18 and len(m["ism"]["services"]) == 18  # ISM's industry lists
    names = [i for t in m["signals"] for i in t["industries"]] + [
        i for rep in m["ism"].values() for v in rep.values() for i in v
    ]
    assert "Furnishings, Fixtures & Appliances" in names and "Furnishings" not in names


def test_last_month_of_missing_or_empty_files():
    assert tb.last_month(None) is None and tb.last_month({"rows": []}) is None
    assert tb.last_month({"rows": [["2026-08", 1], ["2026-09", 2]]}) == "2026-09"


def test_norm_matches_hand_typed_ism_names():
    assert tb.norm("Food, Beverage & Tobacco Products") == tb.norm("food beverage and tobacco products")


def test_signal_effects_follow_sign_and_score():
    sig = {
        "brent": {"score": 1, "state": "Rising", "status": "ok"},
        "umich": {"score": None, "status": "awaiting"},
    }
    e = {(x["theme"], x["industry"]): x for x in tb.signal_effects(MAP, sig)}
    assert e[("oil", "Oil & Gas E&P")]["effect"] == 1 and e[("oil", "Airlines")]["effect"] == -1
    assert "other way" in e[("oil", "Airlines")]["why"]
    assert (
        e[("consumer", "Restaurants")]["effect"] is None
        and e[("consumer", "Restaurants")]["reading"] == "awaiting data"
    )


def ism_row(month, report, industry, status):
    return {
        "month": month,
        "report": report,
        "industry": industry,
        "status": status,
        "rank": None,
        "comment": None,
    }


def test_ism_lists_streaks_unknown_names_and_stale_months():
    rows = [
        ism_row("2026-08", "manufacturing", "Machinery", "growth"),
        ism_row("2026-09", "manufacturing", "machinery", "growth"),
        ism_row("2026-09", "manufacturing", "Petroleum and Coal Products", "contraction"),
        ism_row("2026-09", "manufacturing", "Widgets", "growth"),
        ism_row("2026-08", "services", "Mining", "growth"),
    ]
    effects, status = tb.ism_effects(MAP, rows, {"manufacturing": "2026-09", "services": "2026-09"})
    e = {(x["theme"], x["industry"]): x for x in effects}
    assert e[("ism_manufacturing", "Specialty Industrial Machinery")]["effect"] == 1
    assert e[("ism_manufacturing", "Specialty Industrial Machinery")]["reading"] == "growth (2 months)"
    assert e[("ism_manufacturing", "Oil & Gas Refining & Marketing")]["effect"] == -1
    assert status["manufacturing"]["unknown"] == ["Widgets"] and status["manufacturing"]["status"] == "ok"
    # services list is from August while the headline report is September: never used stale
    assert status["services"]["status"] == "awaiting" and e[("ism_services", "Airlines")]["effect"] is None


def test_industry_scores_tones():
    effects = [
        {"industry": "A", "effect": 1}, {"industry": "A", "effect": 1}, {"industry": "B", "effect": -1},
        {"industry": "C", "effect": 1}, {"industry": "C", "effect": -1}, {"industry": "D", "effect": None},
    ]  # fmt: skip
    s = {x["industry"]: x for x in tb.industry_scores(effects, {"A": 3}, P)}
    assert (s["A"]["net"], s["A"]["tone"], s["A"]["stocks"]) == (2, "strong tailwind", 3)
    assert s["B"]["tone"] == "headwind" and s["C"]["tone"] == "neutral" and s["D"]["net"] is None


def stock(t, industry, cls, **kw):
    base = {"t": t, "name": t, "sector": "X", "industry": industry, "cls": cls, "mcap": 1e10, "eg1": 10.0, "eg2": 10.0,
            "pe1": 15.0, "r3m": 1.0, "vol_ok": True, "why": "", "flags": [], "country": "United States", "rg1": 5.0,
            "rg2": 5.0, "eps1_rev90": 1.0, "rv": 30.0}  # fmt: skip
    return {**base, **kw}


def test_macro_ideas_pair_types_with_the_wind():
    scores = [
        {"industry": "Up", "net": 2, "tone": "strong tailwind"},
        {"industry": "Down", "net": -1, "tone": "headwind"},
    ]
    rows = [stock("L", "Up", "positive"), stock("B", "Up", "boring"), stock("S", "Down", "negative"),
            stock("X", "Down", "positive"), stock("V", "Down", "value_trap")]  # fmt: skip
    ideas = tb.macro_ideas(rows, scores, "net_long")
    assert [x["t"] for x in ideas["long"]] == ["L"] and [x["t"] for x in ideas["short"]] == ["S", "V"]


def test_international_growth_ranks_and_currency_rules():
    rows = [stock(f"C{i}", "I", "mixed", country="China", eg1=float(i), eg2=float(i)) for i in range(1, 9)]
    rows += [
        stock("ADR", "I", "na", country="Hong Kong", eg1=-50.0, eg2=-40.0, rg1=900.0, flags=["currency"]),
        stock("DE", "I", "mixed", country="Germany", eg1=500.0),
        stock("US", "I", "mixed"),
        stock("DUP", "I", "na", country="China", flags=["duplicate"]),
    ]
    intl = tb.international(rows, MAP, P)
    by = {x["t"]: x for x in intl["stocks"]}
    assert "US" not in by and "DUP" not in by
    assert by["ADR"]["pe1"] is None and by["ADR"]["rg1"] is None and by["ADR"]["rank"] == "laggard"
    assert by["DE"]["eg1"] is None  # beyond the growth cap: a data or currency problem
    assert by["C8"]["rank"] == "leader" and by["C4"]["rank"] is None
    assert intl["regions"]["China"]["n"] == 9 and tb.region_of("Brazil", MAP) == "Other"


@pytest.mark.parametrize(
    ("nbs", "rev", "state"),
    [(50.1, -2.0, "disagree"), (49.0, 1.5, "disagree"), (51.0, 1.0, "agree"), (48.0, -1.0, "agree")],
)
def test_china_check(nbs, rev, state):
    sig = {"metrics": {"nbs_manufacturing": nbs, "ratingdog_manufacturing": 51.0}, "as_of": "2026-09"}
    out = tb.china_check(sig, {"China": {"n": 10, "eps1_rev90": rev}}, P)
    assert out["state"] == state
    assert tb.china_check(sig, {"China": {"n": 2, "eps1_rev90": rev}}, P)["state"] == "awaiting"
    assert tb.china_check(None, {}, P)["state"] == "awaiting"


def test_build_from_published_files(tmp_path):
    cols = ["t", "name", "sector", "industry", "country", "cls", "mcap", "eg1", "eg2", "pe1", "r3m", "vol_ok", "why",
            "flags", "rg1", "rg2", "eps1_rev90", "rv"]  # fmt: skip
    rows = [
        stock("XOM", "Oil & Gas E&P", "positive"),
        stock("BABA", "Internet Retail", "mixed", country="China"),
    ]
    (tmp_path / "screener").mkdir()
    (tmp_path / "screener" / "stocks.json").write_text(
        json.dumps({"as_of": "2026-10-22", "columns": cols, "rows": [[r[c] for c in cols] for r in rows]})
    )
    (tmp_path / "macro").mkdir()
    signals = [{"id": "brent", "score": 1, "state": "Rising", "status": "ok", "as_of": "2026-10-21"}]
    (tmp_path / "macro" / "latest.json").write_text(
        json.dumps(
            {
                "as_of": "2026-10-22",
                "bias": {"state": "net_long", "label": "Net long", "score": 0.3},
                "signals": signals,
            }
        )
    )
    (tmp_path / "manual").mkdir()
    (tmp_path / "manual" / "ism_industries.json").write_text(
        json.dumps({"columns": ["month", "report", "industry", "status", "rank", "comment"],
                    "rows": [["2026-09", "services", "Mining", "growth", 1, "Busy."]]})
    )  # fmt: skip
    (tmp_path / "manual" / "ism_services.json").write_text(json.dumps({"rows": [["2026-09", 54.9]]}))
    data = tb.build(tmp_path, MAP)
    top = data["industries"][0]
    assert top["industry"] == "Oil & Gas E&P" and top["net"] == 2 and top["tone"] == "strong tailwind"
    assert [x["t"] for x in data["ideas"]["long"]] == ["XOM"]
    assert data["international"]["stocks"][0]["t"] == "BABA" and data["china"]["state"] == "awaiting"
    assert tb.status_of(data)["long_ideas"] == 1 and data["ism"]["manufacturing"]["status"] == "awaiting"
    assert "Airlines" in data["unknown_industries"] and "Oil & Gas E&P" not in data["unknown_industries"]
