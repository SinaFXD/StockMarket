"""Release calendar: central-bank page parsers, FRED release dates, manual-report rules, last good copy."""

from datetime import date

from conftest import FakeResponse, FakeSession

from pipeline.calendar import CalendarBuilder, fred_events, manual_events, parsers, status_of
from pipeline.http import HttpClient
from pipeline.store import RawCache

FOMC = """<html><h4>2026 FOMC Meetings</h4>
<div class="fomc-meeting__month"><strong>October</strong></div><div class="fomc-meeting__date">27-28</div>
<div class="fomc-meeting__month"><strong>December</strong></div><div class="fomc-meeting__date">8-9*</div>
<h4>2025 FOMC Meetings</h4>
<div class="fomc-meeting__month"><strong>August</strong></div><div class="fomc-meeting__date">22 (notation vote)</div>
<div class="fomc-meeting__month"><strong>Apr/May</strong></div><div class="fomc-meeting__date">30-1</div>
</html>"""
ECB = """<html><dl><dt>28/10/2026</dt><dd>Governing Council of the ECB: monetary policy meeting in Frankfurt (Day 1)</dd>
<dt>29/10/2026</dt><dd>Governing Council of the ECB: monetary policy meeting in Frankfurt (Day 2)</dd>
<dt>25/11/2026</dt><dd>Governing Council of the ECB: non-monetary policy meeting</dd>
<dt>17/12/2026</dt><dd>Governing Council of the ECB: monetary policy meeting in Frankfurt</dd></dl></html>"""
BOJ = """<html><table><caption>Table : 2026</caption><tr><td>Oct. 29 (Thurs.), 30 (Fri.)</td><td>Oct. 30 (Fri.)</td>
<td>Nov. 10 (Tues.)</td></tr><tr><td>July 30 (Thurs.), 31 (Fri.)</td></tr>
<tr><td>Apr. 30 (Thurs.), May 1 (Fri.)</td></tr></table></html>"""
BOE = """<html><h2>2026 confirmed dates</h2><p>Thursday 5 November</p><p>November MPC Summary and minutes and November
Monetary Policy Report</p><p>Thursday&nbsp;17 December</p><p>December MPC Summary and minutes</p>
<h2>2027 provisional dates</h2><p>Thursday 4 February</p></html>"""


def test_fomc_decision_is_the_last_day_and_marks_projections():
    meetings = dict(parsers.fomc(FOMC))
    assert meetings[date(2026, 10, 28)] == ""
    assert "Projections" in meetings[date(2026, 12, 9)]
    assert date(2025, 5, 1) in meetings  # a meeting across two months
    assert all(d != date(2025, 8, 22) for d in meetings)  # notation votes are not meetings


def test_ecb_two_day_meetings_and_non_monetary_meetings():
    assert parsers.ecb(ECB) == [
        (date(2026, 10, 29), "press conference after the decision"),
        (date(2026, 12, 17), "press conference after the decision"),
    ]


def test_boj_reads_meeting_pairs_only():
    days = [d for d, _ in parsers.boj(BOJ)]
    assert days == [date(2026, 5, 1), date(2026, 7, 31), date(2026, 10, 30)]


def test_boe_dates_and_report_months():
    meetings = dict(parsers.boe(BOE))
    assert "Monetary Policy Report" in meetings[date(2026, 11, 5)]
    assert meetings[date(2026, 12, 17)] == "" and date(2027, 2, 4) in meetings


def test_manual_reports_follow_their_release_rules():
    events = manual_events(date(2026, 10, 25), date(2026, 11, 15))
    titles = {(e.title, e.date) for e in events}
    assert ("ISM Manufacturing PMI", date(2026, 11, 2)) in titles
    assert ("NFIB Small Business Optimism", date(2026, 11, 10)) in titles
    assert ("China NBS official PMIs", date(2026, 10, 31)) in titles
    assert all(e.category == "manual_report" and e.signals for e in events)


def test_fred_events_and_the_holding_window():
    events = fred_events({"dates": {"10": ["2026-11-10"], "999": ["2026-11-01"]}})
    cpi = next(e for e in events if e.title.startswith("CPI"))
    assert cpi.importance == "high" and cpi.signals == ("real_rate",)
    today = date(2026, 10, 22)
    assert cpi.to_json(today)["in_window"] is False  # 19 days away
    assert cpi.to_json(date(2026, 10, 21))["in_window"] is True  # 20 days away


class FakeFred:
    def __init__(self, fail=False):
        self.fail = fail

    def _get(self, path, **params):
        if self.fail:
            raise RuntimeError("FRED down")
        return {"release_dates": [{"date": "2026-11-10"}] if params["release_id"] == 10 else []}


def builder(tmp_path, pages, fred=None, offline=False):
    http = HttpClient(
        session=FakeSession([FakeResponse(200, None, text=p) for p in pages]), sleep=lambda s: None
    )
    return CalendarBuilder(RawCache(tmp_path), http, fred or FakeFred(), offline=offline)


def test_builder_keeps_the_last_good_copy(tmp_path):
    today = date(2026, 10, 22)
    first = builder(tmp_path, [FOMC, ECB, BOJ, BOE]).build(today)
    status = {s["id"]: s["status"] for s in first["sources"]}
    assert status == {
        "fred_releases": "ok",
        "fomc": "ok",
        "ecb": "ok",
        "boj": "ok",
        "boe": "ok",
        "manual": "ok",
    }
    assert any(e["title"].startswith("FOMC") and e["date"] == "2026-10-28" for e in first["events"])
    # next run: FRED fails and every page lost its dates -> last good copies, flagged
    broken = "<html><p>We moved things around</p></html>"
    second = builder(tmp_path, [broken] * 4, FakeFred(fail=True)).build(today)
    status = {s["id"]: s["status"] for s in second["sources"]}
    assert status["fred_releases"] == "failed" and status["ecb"] == "failed"
    assert {e["title"] for e in second["events"]} >= {e["title"] for e in first["events"]}
    assert status_of(second)["status"] == "degraded"
    offline = builder(tmp_path, [broken], offline=True).build(today)
    assert {s["status"] for s in offline["sources"]} == {"cached", "ok"}


def test_missing_source_without_cache(tmp_path):
    cal = builder(tmp_path, ["<html>nothing</html>"] * 4, FakeFred(fail=True)).build(date(2026, 10, 22))
    assert {s["id"]: s["status"] for s in cal["sources"]}["fomc"] == "missing"
    assert cal["events"]  # the hand-entered report dates are always there
