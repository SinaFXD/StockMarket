"""Evidence metrics (lesson 29) from a company's latest annual accounts and latest balance sheet (``edgar.py``).

Evidence is backward-looking: it explains why money likes or dislikes a stock, it does not forecast. A ratio is
left blank when its denominator is missing, zero or negative (an EV/EBIT on a loss is not a multiple). For banks
and insurers (Yahoo sector "Financial Services") enterprise value, net debt, the current ratio and interest cover
are not meaningful (debt is their raw material) and are left blank.
"""

from __future__ import annotations

from statistics import median
from typing import Any

# key -> (label, unit, help)
METRICS: dict[str, tuple[str, str, str]] = {
    "rev_growth": ("Sales growth", "%", "Revenue, latest fiscal year vs the year before"),
    "gross_margin": ("Gross margin", "%", "Gross profit (or revenue - cost of revenue) / revenue"),
    "op_margin": ("EBIT margin", "%", "Operating income (EBIT) / revenue"),
    "pretax_margin": ("Pre-tax margin", "%", "Pre-tax income / revenue"),
    "net_margin": ("Net margin", "%", "Net income / revenue"),
    "ev_sales": ("EV/Sales", "x", "Enterprise value / revenue"),
    "ev_ebit": ("EV/EBIT", "x", "Enterprise value / EBIT (only when EBIT > 0)"),
    "ev_ebitda": ("EV/EBITDA", "x", "Enterprise value / (EBIT + depreciation & amortisation)"),
    "net_debt_ebitda": ("Net debt/EBITDA", "x", "(Debt - cash and short-term investments) / EBITDA"),
    "debt_equity": ("Debt/Equity", "x", "Total debt / shareholders' equity"),
    "current_ratio": ("Current ratio", "x", "Current assets / current liabilities"),
    "interest_cover": ("Interest cover", "x", "EBIT / interest expense"),
    "roe": ("ROE", "%", "Net income / shareholders' equity"),
    "roa": ("ROA", "%", "Net income / total assets"),
    "fcf_margin": ("FCF margin", "%", "(Operating cash flow - capex) / revenue"),
    "fcf_yield": ("FCF yield", "%", "(Operating cash flow - capex) / market cap"),
    "cash_conversion": ("Cash conversion", "x", "Operating cash flow / net income"),
}
FINANCIALS = {"Financial Services"}
NOT_FOR_FINANCIALS = {
    "ev_sales",
    "ev_ebit",
    "ev_ebitda",
    "net_debt_ebitda",
    "current_ratio",
    "interest_cover",
}


def _div(a: float | None, b: float | None, pct: bool = False, positive: bool = True) -> float | None:
    if a is None or b is None or b == 0 or (positive and b < 0):
        return None
    v = a / b
    return v * 100 if pct else v


def _sum(*xs: float | None) -> float | None:
    vals = [x for x in xs if x is not None]
    return sum(vals) if vals else None


def compute(acc: dict[str, Any], mcap: float | None, sector: str | None) -> dict[str, Any]:
    if not acc:
        return {}
    rev, ni = acc.get("revenue"), acc.get("net_income")
    gross = acc.get("gross_profit")
    if gross is None and rev is not None and acc.get("cost_of_revenue") is not None:
        gross = rev - acc["cost_of_revenue"]
    ebit = acc.get("operating_income")
    if ebit is None and acc.get("pretax_income") is not None and acc.get("interest_expense") is not None:
        ebit = acc["pretax_income"] + acc["interest_expense"]
    dna = acc.get("dna")
    if dna is None and acc.get("depreciation") is not None:
        dna = acc["depreciation"] + (acc.get("amortization") or 0)
    ebitda = ebit + dna if ebit is not None and dna is not None else None
    if acc.get("debt_total") is not None:
        debt = _sum(acc["debt_total"], acc.get("short_borrowings"))
    else:
        debt = _sum(acc.get("debt_noncurrent"), acc.get("debt_current"), acc.get("short_borrowings"))
    cash = _sum(acc.get("cash"), acc.get("short_investments"))
    ev = (
        mcap + (debt or 0) - (cash or 0)
        if mcap is not None and (debt is not None or cash is not None)
        else None
    )
    net_debt = (debt or 0) - (cash or 0) if debt is not None or cash is not None else None
    ocf, capex = acc.get("operating_cash_flow"), acc.get("capex")
    fcf = ocf - capex if ocf is not None and capex is not None else None
    growth = _div(rev, acc.get("revenue_prev"))
    out = {
        "fy_end": acc.get("fy_end"),
        "bs_date": acc.get("bs_date"),
        "revenue": rev,
        "ebitda": ebitda,
        "ev": ev,
        "rev_growth": None if growth is None else (growth - 1) * 100,
        "gross_margin": _div(gross, rev, pct=True),
        "op_margin": _div(ebit, rev, pct=True),
        "pretax_margin": _div(acc.get("pretax_income"), rev, pct=True),
        "net_margin": _div(ni, rev, pct=True),
        "ev_sales": _div(ev, rev),
        "ev_ebit": _div(ev, ebit) if ev is not None and ev > 0 else None,
        "ev_ebitda": _div(ev, ebitda) if ev is not None and ev > 0 else None,
        "net_debt_ebitda": _div(net_debt, ebitda),
        "debt_equity": _div(debt, acc.get("equity")),
        "current_ratio": _div(acc.get("assets_current"), acc.get("liabilities_current")),
        "interest_cover": _div(ebit, acc.get("interest_expense")),
        "roe": _div(ni, acc.get("equity"), pct=True),
        "roa": _div(ni, acc.get("assets"), pct=True),
        "fcf_margin": _div(fcf, rev, pct=True),
        "fcf_yield": _div(fcf, mcap, pct=True),
        "cash_conversion": _div(ocf, ni),
    }
    if sector in FINANCIALS:
        for k in NOT_FOR_FINANCIALS:
            out[k] = None
    return out


def sector_medians(rows: list[dict[str, Any]], included) -> dict[str, dict[str, float | None]]:
    """Median of each Evidence metric per sector, over the stocks that count toward the averages."""
    out: dict[str, dict[str, float | None]] = {}
    for sector in sorted({r["sector"] for r in rows if r["sector"]}) + ["all"]:
        group = [r for r in rows if included(r) and (sector == "all" or r["sector"] == sector)]
        out[sector] = {}
        for m in METRICS:
            vals = [r[m] for r in group if r.get(m) is not None]
            out[sector][m] = round(median(vals), 3) if vals else None
    return out
