"""SEC EDGAR Evidence: frames periods, one fiscal year per company, the lesson-29 metrics, caching."""

from datetime import UTC, date, datetime

import pytest
from conftest import FakeResponse, FakeSession

from pipeline.http import HttpClient
from pipeline.screener import edgar, evidence
from pipeline.screener.build import ScreenerBuilder
from pipeline.store import RawCache


def test_periods_cover_three_years_and_the_last_four_quarter_ends():
    years, quarters = edgar.periods(date(2026, 10, 22))
    assert years == ["CY2024", "CY2025", "CY2026"]
    assert quarters == ["CY2026Q3I", "CY2026Q2I", "CY2026Q1I", "CY2025Q4I"]
    assert edgar.periods(date(2027, 2, 1))[1][0] == "CY2026Q4I"


def frames():
    rev = {"1": ["2024-10-01", "2025-09-30", 1000.0, "a"]}
    rev_prev = {"1": ["2023-10-01", "2024-09-30", 800.0, "a"]}
    later_ni = {"1": ["2025-10-01", "2026-09-30", 999.0, "b"]}  # a newer year for one line only: ignored
    return {
        "Revenues|CY2025": rev,
        "Revenues|CY2024": rev_prev,
        "RevenueFromContractWithCustomerExcludingAssessedTax|CY2025": {
            "1": ["2024-10-01", "2025-09-30", 5.0, "x"]
        },
        "NetIncomeLoss|CY2025": {"1": ["2024-10-01", "2025-09-30", 100.0, "a"]},
        "NetIncomeLoss|CY2026": later_ni,
        "OperatingIncomeLoss|CY2025": {"1": ["2024-10-01", "2025-09-30", 200.0, "a"]},
        "CostOfRevenue|CY2025": {"1": ["2024-10-01", "2025-09-30", 600.0, "a"]},
        "Depreciation|CY2025": {"1": ["2024-10-01", "2025-09-30", 40.0, "a"]},
        "AmortizationOfIntangibleAssets|CY2025": {"1": ["2024-10-01", "2025-09-30", 10.0, "a"]},
        "NetCashProvidedByUsedInOperatingActivities|CY2025": {"1": ["2024-10-01", "2025-09-30", 150.0, "a"]},
        "PaymentsToAcquireProductiveAssets|CY2025": {"1": ["2024-10-01", "2025-09-30", 50.0, "a"]},
        "StockholdersEquity|CY2026Q2I": {"1": [None, "2026-06-30", 500.0, "c"]},
        "StockholdersEquity|CY2026Q1I": {"1": [None, "2026-03-31", 450.0, "c"]},
        "LongTermDebtNoncurrent|CY2026Q2I": {"1": [None, "2026-06-30", 300.0, "c"]},
        "LongTermDebtCurrent|CY2026Q2I": {"1": [None, "2026-06-30", 50.0, "c"]},
        "LongTermDebtCurrent|CY2026Q1I": {"1": [None, "2026-03-31", 999.0, "c"]},
        "CashAndCashEquivalentsAtCarryingValue|CY2026Q2I": {"1": [None, "2026-06-30", 150.0, "c"]},
        "AssetsCurrent|CY2026Q2I": {"1": [None, "2026-06-30", 400.0, "c"]},
        "LiabilitiesCurrent|CY2026Q2I": {"1": [None, "2026-06-30", 200.0, "c"]},
        "Assets|CY2026Q2I": {"1": [None, "2026-06-30", 2000.0, "c"]},
    }


def test_accounts_use_one_fiscal_year_one_tag_and_one_balance_sheet_date():
    acc = edgar.accounts(edgar.index_frames(frames()), 1)
    assert (
        acc["fy_end"] == "2025-09-30" and acc["revenue"] == 1000.0
    )  # "Revenues" preferred over the other tag
    assert acc["revenue_prev"] == 800.0
    assert acc["net_income"] == 100.0  # the FY2026 figure belongs to another year
    assert acc["bs_date"] == "2026-06-30" and acc["equity"] == 500.0 and acc["debt_current"] == 50.0
    assert edgar.accounts(edgar.index_frames(frames()), 2) == {}


def test_lesson_29_metrics():
    acc = edgar.accounts(edgar.index_frames(frames()), 1)
    m = evidence.compute(acc, 3000.0, "Technology")
    assert m["rev_growth"] == pytest.approx(25.0)
    assert m["gross_margin"] == pytest.approx(40.0)  # revenue - cost of revenue
    assert m["op_margin"] == pytest.approx(20.0) and m["net_margin"] == pytest.approx(10.0)
    ev = 3000 + 350 - 150
    assert m["ev_sales"] == pytest.approx(ev / 1000) and m["ev_ebit"] == pytest.approx(ev / 200)
    assert m["ev_ebitda"] == pytest.approx(ev / 250)  # D&A = depreciation + amortisation
    assert m["net_debt_ebitda"] == pytest.approx(200 / 250) and m["debt_equity"] == pytest.approx(0.7)
    assert m["current_ratio"] == pytest.approx(2.0) and m["roe"] == pytest.approx(20.0)
    assert m["fcf_margin"] == pytest.approx(10.0) and m["fcf_yield"] == pytest.approx(100 / 30)
    assert m["interest_cover"] is None  # not tagged
    bank = evidence.compute(acc, 3000.0, "Financial Services")
    assert bank["ev_ebitda"] is None and bank["roe"] == pytest.approx(20.0)
    loss = evidence.compute({"revenue": 100.0, "operating_income": -5.0, "net_income": -8.0, "equity": -10.0,
                             "cash": 1.0}, 50.0, "Technology")  # fmt: skip
    assert loss["ev_ebit"] is None and loss["roe"] is None and loss["op_margin"] == pytest.approx(-5.0)
    assert evidence.compute({}, 50.0, "Technology") == {}


def test_sector_medians_use_clean_rows():
    rows = [
        {"sector": "Tech", "flags": [], "roe": 10.0},
        {"sector": "Tech", "flags": [], "roe": 30.0},
        {"sector": "Tech", "flags": ["currency"], "roe": 99.0},
    ]
    med = evidence.sector_medians(rows, lambda r: not r["flags"])
    assert med["Tech"]["roe"] == 20.0 and med["all"]["roe"] == 20.0 and med["Tech"]["ev_ebit"] is None


NOW = datetime(2026, 10, 22, 6, 0, tzinfo=UTC)


def sec_http(responses):
    return HttpClient(session=FakeSession(responses), sleep=lambda s: None)


def test_builder_needs_the_sec_contact_and_keeps_the_last_good_copy(tmp_path):
    cache = RawCache(tmp_path)
    b = ScreenerBuilder(cache, sec_user_agent="", now=NOW)
    assert b.edgar(date(2026, 10, 22)) is None
    assert b.status["edgar"]["status"] == "missing" and "SEC_USER_AGENT" in b.status["edgar"]["error"]
    tickers = FakeResponse(200, {"0": {"cik_str": 1, "ticker": "abc", "title": "ABC"}})
    frame = FakeResponse(
        200, {"data": [{"cik": 1, "start": "2024-10-01", "end": "2025-09-30", "val": 10, "accn": "a"}]}
    )
    ok = ScreenerBuilder(
        cache, sec_user_agent="Test test@example.com", sec_http=sec_http([tickers, frame]), now=NOW
    )
    payload = ok.edgar(date(2026, 10, 22))
    assert payload["tickers"] == {"ABC": 1} and ok.status["edgar"]["status"] == "ok"
    assert payload["frames"]["Revenues|CY2025"]["1"][2] == 10
    later = datetime(2026, 10, 23, 6, 0, tzinfo=UTC)
    broken = ScreenerBuilder(
        cache, sec_user_agent="Test test@example.com", sec_http=sec_http([FakeResponse(503, {})]), now=later
    )
    assert broken.edgar(date(2026, 10, 23)) == payload and broken.status["edgar"]["status"] == "failed"
    assert "test@example.com" not in str(broken.status)  # the contact never reaches health.json
