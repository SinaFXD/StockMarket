"""SEC EDGAR "Evidence" data (lesson 29): backward-looking accounts from companies' own XBRL filings.

One company's full ``companyfacts`` file is ~4 MB, too much for ~2,000 stocks a day. The ``frames`` API instead
returns one line item for every company and one period (~0.5 MB), so ~100 requests cover the universe:
- duration items (revenue, profit, cash flow) for the calendar years ``CY{Y}`` around today: each company's
  latest fiscal year is the period with the latest end date, the previous year the one ending ~12 months earlier;
- instant items (cash, debt, equity, assets) for the last quarter-ends ``CY{Y}Q{q}I``: the latest balance sheet.

SEC requires a ``User-Agent`` with a contact e-mail (env ``SEC_USER_AGENT``) and at most 10 requests a second.
Foreign filers reporting under IFRS are not in the ``us-gaap`` frames and get no Evidence numbers.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..http import FetchError, HttpClient

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FRAME_URL = "https://data.sec.gov/api/xbrl/frames/us-gaap/{concept}/USD/{period}.json"

# metric -> concepts in order of preference (companies tag the same line differently)
DURATION = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "gross_profit": ["GrossProfit"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],  # gross profit fallback
    "operating_income": ["OperatingIncomeLoss"],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ],
    "net_income": ["NetIncomeLoss"],
    "dna": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
    ],
    "depreciation": ["Depreciation"],  # D&A fallback: depreciation and amortisation tagged separately
    "amortization": ["AmortizationOfIntangibleAssets"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
}
INSTANT = {
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "short_investments": ["MarketableSecuritiesCurrent", "ShortTermInvestments"],
    "debt_total": [
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
        "DebtLongtermAndShorttermCombinedAmount",
    ],
    "debt_noncurrent": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
    "debt_current": ["LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent", "DebtCurrent"],
    "short_borrowings": ["ShortTermBorrowings", "CommercialPaper"],
    "equity": ["StockholdersEquity"],
    "assets": ["Assets"],
    "assets_current": ["AssetsCurrent"],
    "liabilities_current": ["LiabilitiesCurrent"],
}


def periods(today: date) -> tuple[list[str], list[str]]:
    """Annual frames for the last three calendar years and instant frames for the last four quarter-ends."""
    years = [f"CY{y}" for y in (today.year - 2, today.year - 1, today.year)]
    quarters = []
    y, q = today.year, (today.month - 1) // 3  # the quarter that ended most recently
    if q == 0:
        y, q = y - 1, 4
    for _ in range(4):
        quarters.append(f"CY{y}Q{q}I")
        y, q = (y, q - 1) if q > 1 else (y - 1, 4)
    return years, quarters


def fetch_tickers(http: HttpClient) -> dict[str, int]:
    data = http.get_json(TICKERS_URL)
    if not isinstance(data, dict) or not data:
        raise FetchError("SEC company_tickers.json was empty")
    return {str(v["ticker"]).upper(): int(v["cik_str"]) for v in data.values()}


def fetch_frames(http: HttpClient, today: date) -> dict[str, dict[str, list]]:
    """``{"Concept|Period": {cik: [start, end, value, filed-accession]}}`` for every concept above."""
    years, quarters = periods(today)
    out: dict[str, dict[str, list]] = {}
    jobs = [(c, p) for cs in DURATION.values() for c in cs for p in years]
    jobs += [(c, p) for cs in INSTANT.values() for c in cs for p in quarters]
    missing = 0
    for concept, period in jobs:
        try:
            data = http.get_json(FRAME_URL.format(concept=concept, period=period))
        except FetchError as exc:
            if "HTTP 404" in str(exc):  # no company used this concept for this period yet
                missing += 1
                continue
            raise
        out[f"{concept}|{period}"] = {
            str(r["cik"]): [r.get("start"), r.get("end"), r.get("val"), r.get("accn")]
            for r in data.get("data", [])
        }
    if not out:
        raise FetchError("SEC returned no frames")
    return out


def index_frames(frames: dict[str, dict[str, list]]) -> dict[str, dict[str, list[list]]]:
    """``{concept: {cik: [rows sorted by end date]}}`` so each company is looked up once per concept."""
    out: dict[str, dict[str, list[list]]] = {}
    for key, rows in frames.items():
        concept = key.split("|")[0]
        bucket = out.setdefault(concept, {})
        for cik, row in rows.items():
            if row[1] and row[2] is not None:
                bucket.setdefault(cik, []).append(row)
    for bucket in out.values():
        for rows in bucket.values():
            rows.sort(key=lambda r: r[1])
    return out


def _rows(index: dict, concepts: list[str], cik: str) -> list[list]:
    """Rows of the first preferred concept this company reports, so its numbers never mix two tags."""
    for concept in concepts:
        rows = index.get(concept, {}).get(cik)
        if rows:
            return rows
    return []


def _at(rows: list[list], end: date, tolerance: int = 20) -> list | None:
    for r in reversed(rows):
        if abs((date.fromisoformat(r[1]) - end).days) <= tolerance:
            return r
    return None


def accounts(index: dict, cik: int) -> dict[str, Any]:
    """Raw line items for one company, all from the same fiscal year and the same balance-sheet date:
    ``{metric: value}``, ``{metric}_prev`` for the year before, ``fy_end`` and ``bs_date``."""
    key = str(cik)
    out: dict[str, Any] = {}
    duration = {m: _rows(index, c, key) for m, c in DURATION.items()}
    anchor_rows = duration["revenue"] or duration["net_income"] or duration["operating_cash_flow"]
    if anchor_rows:
        end = date.fromisoformat(anchor_rows[-1][1])
        out["fy_end"] = end.isoformat()
        prev_end = date(end.year - 1, end.month, min(end.day, 28))
        for metric, rows in duration.items():
            if (r := _at(rows, end)) is not None:
                out[metric] = r[2]
            if (r := _at(rows, prev_end, 40)) is not None:
                out[f"{metric}_prev"] = r[2]
    instant = {m: _rows(index, c, key) for m, c in INSTANT.items()}
    bs_rows = instant["equity"] or instant["assets"]
    if bs_rows:
        bs = date.fromisoformat(bs_rows[-1][1])
        out["bs_date"] = bs.isoformat()
        for metric, rows in instant.items():
            if (r := _at(rows, bs, 10)) is not None:
                out[metric] = r[2]
    return out
