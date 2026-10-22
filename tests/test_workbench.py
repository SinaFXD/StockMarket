"""Trade Idea Workbench (lessons 30-33): price targets, expected move, story, earnings session, short interest,
technicals, the per-stock pages and the saved idea files."""

import json
from datetime import UTC, date, datetime

import pytest

from pipeline.config import WORKBENCH
from pipeline.screener import yahoo
from pipeline.workbench import build, ideas, stock, targets

P = dict(WORKBENCH)
FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"


# -- price targets (lesson 33) ----------------------------------------------------------------------------
def test_zendesk_example_from_the_course():
    # price 76; EPS growth +80% this year and +21.85% next; sales growth +35% at an unchanged share count
    t = targets.price_targets(76.0, [1.0, 1.8, 1.8 * 1.21853], [100.0, 135.0, 160.0], 10.0)
    assert t["pe"] == pytest.approx(76.0) and t["ps"] == pytest.approx(7.6)
    y1, y2 = t["years"]
    assert y1["eps_target"] == pytest.approx(136.80) and y1["sales_target"] == pytest.approx(102.60)
    assert y2["eps_target"] == pytest.approx(166.69, abs=0.01)
    assert y1["eps_move"] == pytest.approx(80.0) and y1["sales_move"] == pytest.approx(35.0)


def test_targets_from_a_loss_base_need_the_users_pe():
    t = targets.price_targets(50.0, [-0.5, 0.4, 1.2], [100.0, 120.0, 150.0], 10.0)
    assert t["pe"] is None and t["years"][1]["eps_target"] is None
    assert t["years"][0]["sales_target"] == pytest.approx(60.0)
    own = targets.price_targets(50.0, [-0.5, 0.4, 1.2], [100.0, 120.0, 150.0], 10.0, pe=40.0, ps=4.0)
    assert own["years"][1]["eps_target"] == pytest.approx(48.0)
    assert own["years"][0]["sales_target"] == pytest.approx(4.0 * 120 / 10)
    # negative forward EPS: no EPS-based target; missing sales: no sales-based target
    t = targets.price_targets(50.0, [2.0, -1.0, None], [None, 10.0, 12.0], 10.0)
    assert t["years"][0]["eps_target"] is None and t["years"][0]["sales_target"] is None
    # buybacks: 10% fewer shares lift the sales-based target per share
    t = targets.price_targets(76.0, [1.0, 1.8, 2.0], [100.0, 135.0, 160.0], 10.0, shares_fwd=9.0)
    assert t["years"][0]["sales_target"] == pytest.approx(102.6 / 0.9)


def test_expected_move_and_realism():
    assert targets.sigma_move(36.5, 36.5) == pytest.approx(36.5 * 0.1**0.5)
    assert targets.sigma_move(None, 40) is None and targets.sigma_move(30, 0) is None
    sig = targets.sigma_move(40.0, 40)  # ~13.2%
    assert targets.realism(10.0, sig, P)["state"] == "realistic"
    assert targets.realism(-20.0, sig, P)["state"] == "stretched"
    assert targets.realism(80.0, sig, P)["state"] == "unrealistic"
    assert targets.realism(None, sig, P) is None


def test_period_return():
    closes = [100.0] * 10 + [110.0]
    assert targets.period_return(closes, 5) == pytest.approx(10.0)
    assert targets.period_return(closes, 20) is None


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (
            {"eps0": 1, "eps1": 1.5, "eps2": 1.8, "eg1": 50, "eg2": 20, "rg1": 10, "rg2": 8},
            "Earnings-growth story",
        ),
        (
            {"eps0": 1, "eps1": 1.1, "eps2": 1.2, "eg1": 10, "eg2": 9, "rg1": 30, "rg2": 25},
            "Revenue-growth story",
        ),
        ({"eps0": 1, "eps1": 0.9, "eps2": 1.0, "eg1": -10, "eg2": 11, "rg1": 5, "rg2": 5}, "Margin squeeze"),
        ({"eps0": -1, "eps1": 0.5, "eps2": 1.0, "eg1": None, "eg2": 100, "rg1": 5, "rg2": 5}, "Turnaround"),
        (
            {"eps0": -1, "eps1": -0.5, "eps2": -0.2, "eg1": None, "eg2": None, "rg1": 40, "rg2": 30},
            "Loss-making",
        ),
    ],
)
def test_story(row, expected):
    assert targets.story(row, P)[0].startswith(expected)


def test_gaap_gap():
    assert targets.gaap_gap(2.0, 100.0, 100.0, P)["gap_pct"] == pytest.approx(100.0)
    assert "close" in targets.gaap_gap(1.05, 100.0, 100.0, P)["text"]
    assert "GAAP loss" in targets.gaap_gap(1.0, 100.0, -5.0, P)["text"]
    assert targets.gaap_gap(1.0, None, 100.0, P) is None


# -- stock page pieces ------------------------------------------------------------------------------------
def test_earnings_session_from_yahoos_fixed_utc_hours():
    after = datetime(2026, 12, 1, 20, 0, tzinfo=UTC).timestamp()  # 15:00 in New York (winter)
    before = datetime(2026, 10, 28, 11, 30, tzinfo=UTC).timestamp()  # 07:30 in New York
    assert stock.earnings_time(after, False) == {
        "date": "2026-12-01",
        "session": "after the close",
        "estimated": False,
    }
    assert stock.earnings_time(before, False)["session"] == "before the open"
    assert stock.earnings_time(before, True)["session"].startswith("date estimated")
    assert stock.earnings_time(None, False) is None


def test_short_interest_reading():
    crowded = stock.short_interest(
        {"short_pct_float": 0.18, "short_ratio": 6.2, "shares_short": 120, "shares_short_prior": 100}, P
    )
    assert crowded["crowded"] and crowded["change_pct"] == pytest.approx(20.0)
    assert crowded["text"].startswith("18.0% of the float") and "up 20%" in crowded["text"]
    calm = stock.short_interest({"short_pct_float": 0.02, "short_ratio": 1.1}, P)
    assert not calm["crowded"] and "Not a crowded short" in calm["text"]
    assert stock.short_interest({}, P) is None


def bars(n=260, start=100.0, step=0.2):
    closes = [start + i * step for i in range(n)]
    return {
        "d": [f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)],
        "o": closes,
        "h": [c + 1 for c in closes],
        "l": [c - 1 for c in closes],
        "c": closes,
        "v": [1000] * n,
    }


def test_technicals_and_trend_reading():
    t = stock.technicals(bars(), {"SPY": 5.0, "XLK": 8.0}, "Technology")
    assert t["ma50"] < t["last"] and t["ma200"] < t["ma50"] and t["reading"].startswith("Uptrend")
    assert t["high52"] == pytest.approx(t["last"] + 1) and t["off_high"] < 0
    assert t["rs_spy_3m"] == pytest.approx(t["r3m"] - 5.0) and t["sector_etf"] == "XLK"
    down = stock.technicals(bars(step=-0.2, start=200.0), {}, "Energy")
    assert down["reading"].startswith("Downtrend") and "rs_spy_3m" not in down
    assert stock.technicals({"c": [1.0] * 10}, {}, None) == {}


ROW = {
    "t": "ZEN", "sector": "Technology", "price": 76.0, "mcap": 760.0, "eps0": 1.0, "eps1": 1.8, "eps2": 2.19,
    "eg1": 80.0, "eg2": 21.7, "rg1": 35.0, "rg2": 18.5, "rv": 40.0, "iv": None,
}  # fmt: skip
SUMMARY = {
    "country": "United States",
    "0y": {
        "end": "2026-12-31",
        "eps_low": 1.6,
        "eps_high": 2.0,
        "analysts": 20,
        "rev": 135.0,
        "rev_year_ago": 100.0,
    },
    "+1y": {"end": "2027-12-31", "rev": 160.0},
    "0q": {"end": "2026-12-31", "eps": 0.5, "eps_low": 0.45, "eps_high": 0.55},
    "stats": {"shares": 10.0, "short_pct_float": 0.03, "short_ratio": 2.0, "insiders": 0.05},
    "profile": {"summary": "Customer service software.", "employees": 6000},
    "analysts": {"target_mean": 90.0},
    "earnings_date": datetime(2026, 11, 5, 21, 0, tzinfo=UTC).timestamp(),
    "earnings_date_estimated": False,
}


def test_stock_page_fills_the_template():
    acc = {"fy_end": "2025-12-31", "net_income": 8.0, "revenue": 100.0}
    page = stock.build(ROW, {}, SUMMARY, bars(), acc, {"SPY": 3.0}, P, "2026-10-22")
    assert page["quant"]["labels"] == ["FY2025", "FY2026", "FY2027"]
    assert page["quant"]["sales"] == [100.0, 135.0, 160.0] and page["quant"]["shares"] == 10.0
    y1 = page["targets"]["years"][0]
    assert y1["eps_target"] == pytest.approx(136.8) and y1["sales_target"] == pytest.approx(102.6)
    assert y1["eps_realism"]["state"] == "unrealistic"  # +80% in 40 days with 40% volatility
    assert page["targets"]["vol_source"] == "realised" and page["sigma"]["60"] > page["sigma"]["30"]
    assert page["gaap"]["gap_pct"] == pytest.approx(25.0)  # adjusted 1.0 x 10 shares vs GAAP 8.0
    assert page["earnings"]["session"] == "after the close" and page["quarter"]["eps_high"] == 0.55
    assert page["story"][0].startswith("Earnings-growth story")
    assert page["profile"]["employees"] == 6000 and page["technicals"]["reading"].startswith("Uptrend")
    # SEC year that is not the year before the current fiscal year: no GAAP comparison
    other = stock.build(
        ROW, {}, SUMMARY, None, {"fy_end": "2024-12-31", "net_income": 8.0}, {}, P, "2026-10-22"
    )
    assert other["gaap"] is None and other["technicals"] == {} and other["prices"] is None


def test_trim_summary_keeps_the_template_fields():
    raw = {
        "assetProfile": {"longBusinessSummary": "Makes things.", "fullTimeEmployees": 100, "website": "https://x.com"},
        "defaultKeyStatistics": {"sharesOutstanding": 5e8, "shortPercentOfFloat": 0.04, "dateShortInterest": 1790726400},
        "financialData": {"targetMeanPrice": 250.0, "recommendationKey": "buy", "numberOfAnalystOpinions": 30},
        "earningsTrend": {"trend": [{"period": "0q", "endDate": "2026-12-31", "earningsEstimate": {"avg": 1.1, "low": 1.0}}]},
    }  # fmt: skip
    s = yahoo.trim_summary(raw)
    assert s["profile"]["summary"] == "Makes things." and s["stats"]["shares"] == 5e8
    assert s["stats"]["short_date"] == "2026-09-30" and s["analysts"]["rec_key"] == "buy"
    assert s["0q"]["eps"] == 1.1 and s["0q"]["eps_low"] == 1.0


def test_compact_bars_rounds_and_keeps_the_last_n():
    import pandas as pd

    idx = pd.bdate_range("2026-01-01", periods=5)
    frame = pd.DataFrame(
        {"Open": [1.23456] * 5, "High": [12.3456] * 5, "Low": [1.0] * 5, "Close": [1.1, 1.2, None, 1.3, 1.4],
         "Volume": [10.0, 20.0, 30.0, None, 50.0]},
        index=idx,
    )  # fmt: skip
    from pipeline.screener import volatility

    b = volatility.compact_bars(frame, 3)
    assert b["d"] == ["2026-01-02", "2026-01-06", "2026-01-07"] and b["c"] == [1.2, 1.3, 1.4]
    assert b["o"][0] == 1.2346 and b["h"][0] == 12.35 and b["v"] == [20, None, 50]


# -- saved ideas (data/ideas/*.md) ------------------------------------------------------------------------
def test_parse_the_file_the_website_writes():
    # fixture written by site/assets/ideas-store.js (toMarkdown); see docs/08-workbench-method.md
    text = (FIXTURES / "idea_CRWD.md").read_text(encoding="utf-8")
    idea, errors, warnings = ideas.parse(text, "CRWD")
    assert errors == [] and warnings == []
    expected = json.loads((FIXTURES / "idea_CRWD.json").read_text(encoding="utf-8"))
    assert idea == expected


def test_parse_reports_problems_in_plain_english():
    text = """---
side: sideways
status: active
opened: 22/10/2026
horizon_days: 90
entry_price: abc
assumptions:
  pe: 25
  peg: 1
colour: red
---
Some text before any heading
## Business
Sells software.
## Catalysts
- 2026-11-05: Investor day
- product launch
"""
    idea, errors, warnings = ideas.parse(text, "ON")
    assert idea["ticker"] == "ON" and idea["side"] == "long" and idea["status"] == "active"
    assert any(e.startswith("side:") for e in errors) and any(e.startswith("opened:") for e in errors)
    assert any(e.startswith("entry_price:") for e in errors)
    assert any("outside the course's 20-60" in w for w in warnings) and any("colour" in w for w in warnings)
    assert any("peg" in w for w in warnings) and any("outside the known sections" in w for w in warnings)
    assert idea["assumptions"] == {"pe": 25.0} and idea["business"] == "Sells software."
    assert idea["catalysts"] == [
        {"date": "2026-11-05", "text": "Investor day"},
        {"date": None, "text": "product launch"},
    ]
    with pytest.raises(ideas.IdeaError):
        ideas.parse("side: long\n", "ON")
    with pytest.raises(ideas.IdeaError):
        ideas.parse("---\nside: [long\n---\n", "ON")


def test_load_and_check_command(tmp_path, capsys):
    folder = tmp_path / "ideas"
    folder.mkdir()
    (folder / "CRWD.md").write_text((FIXTURES / "idea_CRWD.md").read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "README.md").write_text("# how to", encoding="utf-8")
    (folder / "BAD.md").write_text("no header", encoding="utf-8")
    (folder / "x y.md").write_text("---\n---\n", encoding="utf-8")
    data = build.build_ideas(folder)
    assert [i["ticker"] for i in data["ideas"]] == ["CRWD"]
    assert {p["file"] for p in data["problems"]} == {"BAD.md", "x y.md"}
    assert build.ideas_status(data)["status"] == "failed"
    from pipeline.workbench.__main__ import main

    assert main(["--check", "--ideas-dir", str(folder)]) == 1
    assert "ERROR   BAD.md" in capsys.readouterr().out
    (folder / "BAD.md").unlink()
    (folder / "x y.md").unlink()
    out = tmp_path / "site"
    assert main(["--ideas-dir", str(folder), "--out-dir", str(out)]) == 0
    assert json.loads((out / "ideas.json").read_text())["ideas"][0]["side"] == "long"
    assert build.build_ideas(tmp_path / "missing")["ideas"] == []


def test_stock_pages_are_written_and_old_ones_removed(tmp_path):
    class Builder:
        quotes = [{"symbol": "ZEN", "sharesOutstanding": 10.0}]
        rows = [ROW]
        summary_store = {"ZEN": {"data": SUMMARY}}
        accounts = {}

        def bars(self):
            return {"ZEN": bars()}

    old = tmp_path / "stocks" / "GONE.json"
    old.parent.mkdir()
    old.write_text("{}")
    res = build.write_stock_pages(tmp_path, Builder(), tmp_path, date(2026, 10, 22).isoformat())
    assert res == {"pages": 1, "with_prices": 1} and not old.exists()
    page = json.loads((tmp_path / "stocks" / "ZEN.json").read_text())
    assert page["t"] == "ZEN" and len(page["prices"]["c"]) == 260
    assert build.safe_name("brk-b") == "BRK-B" and build.safe_name("../x") == "..X"


def test_exit_fields_and_track_record_warnings():
    head = "---\nside: short\nstatus: {status}\nopened: 2026-10-10\nentry_price: 50\n{extra}---\n"
    idea, errors, warnings = ideas.parse(
        head.format(status="closed", extra="exit_price: 45\nexit_date: 2026-11-01\n"), "AB"
    )
    assert (
        errors == [] and warnings == [] and idea["exit_price"] == 45.0 and idea["exit_date"] == "2026-11-01"
    )
    _, errors, _ = ideas.parse(
        head.format(status="closed", extra="exit_price: 45\nexit_date: 2026-10-01\n"), "AB"
    )
    assert errors == ["exit_date is before the entry"]
    _, _, warnings = ideas.parse(head.format(status="active", extra="exit_price: 45\n"), "AB")
    assert any("both exit_price and exit_date" in w for w in warnings)
    assert any("status is not 'closed'" in w for w in warnings)
    _, _, warnings = ideas.parse(head.format(status="closed", extra=""), "AB")
    assert any("left out of the track record" in w for w in warnings)
