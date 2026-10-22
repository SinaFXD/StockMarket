"""Trade-idea arithmetic (lesson 33): price targets, the expected move over the horizon and the "story" comment.

Price targets, as the course builds them (Zendesk, May 2020: price 76 -> 102.60 sales-based, 136.80 EPS-based):
- **EPS-based** (upper / bullish): EPS growth at a constant P/E. P/E = price / EPS0 (last reported fiscal year),
  target = P/E x EPS1 (and x EPS2 for next year), i.e. price x (1 + EG). Not meaningful from a loss (EPS0 <= 0)
  unless the user sets a P/E.
- **Sales-based** (lower / realistic): consensus sales at a constant price-to-sales. P/S = price / (sales0 /
  shares), target = P/S x sales1 / shares, i.e. price x (1 + sales growth) at an unchanged share count.

``site/assets/workbench.js`` repeats ``price_targets`` and ``sigma_move`` for the user's own assumptions (keep
them in sync).
"""

from __future__ import annotations

import math
from typing import Any


def _pos(x: Any) -> bool:
    return isinstance(x, int | float) and x == x and x > 0


def price_targets(
    price: float | None,
    eps: list[float | None],
    sales: list[float | None],
    shares: float | None,
    pe: float | None = None,
    ps: float | None = None,
    shares_fwd: float | None = None,
) -> dict[str, Any]:
    """``eps`` and ``sales``: [last reported year, current year E, next year E]. ``pe``/``ps`` override the
    constant multiples; ``shares_fwd`` is the share count expected in the forward years (buybacks, dilution),
    by default today's. Returns the multiples used and, per forward year, both targets and the move in %."""
    pe_used = pe if _pos(pe) else (price / eps[0] if _pos(price) and _pos(eps[0]) else None)
    ps_used = (
        ps
        if _pos(ps)
        else (price / (sales[0] / shares) if _pos(price) and _pos(sales[0]) and _pos(shares) else None)
    )
    sh = shares_fwd if _pos(shares_fwd) else shares
    years = []
    for i in (1, 2):
        e, s = eps[i] if len(eps) > i else None, sales[i] if len(sales) > i else None
        eps_t = pe_used * e if pe_used is not None and _pos(e) else None
        sales_t = ps_used * s / sh if ps_used is not None and _pos(s) and _pos(sh) else None
        years.append(
            {
                "eps_target": eps_t,
                "sales_target": sales_t,
                "eps_move": move(price, eps_t),
                "sales_move": move(price, sales_t),
            }
        )
    return {"pe": pe_used, "ps": ps_used, "years": years}


def move(price: float | None, target: float | None) -> float | None:
    return (target / price - 1) * 100 if _pos(price) and target is not None else None


def sigma_move(vol_pct: float | None, days: float) -> float | None:
    """One standard deviation of the price move over ``days`` calendar days, in %, from an annualised
    volatility (implied when there is one, else realised)."""
    if not _pos(vol_pct) or days <= 0:
        return None
    return vol_pct * math.sqrt(days / 365)


def realism(move_pct: float | None, sigma_pct: float | None, p: dict) -> dict[str, Any] | None:
    """How many standard deviations a target is away over the horizon, and the course's reading of it: adjust
    targets that are unrealistic for the 20-60 day horizon (lesson 33)."""
    if move_pct is None or not _pos(sigma_pct):
        return None
    z = abs(move_pct) / sigma_pct
    if z <= p["sigma_ok"]:
        state = "realistic"
    elif z <= p["sigma_stretched"]:
        state = "stretched"
    else:
        state = "unrealistic"
    return {"z": z, "state": state}


def period_return(closes: list | None, days: int) -> float | None:
    """Return over the last ``days`` trading days, in %."""
    vals = [c for c in (closes or []) if c is not None]
    if len(vals) <= days or not _pos(vals[-days - 1]):
        return None
    return (vals[-1] / vals[-days - 1] - 1) * 100


def story(row: dict[str, Any], p: dict) -> list[str]:
    """What kind of story the numbers tell (lesson 33, quant table comment): revenue growth or earnings growth,
    margins widening or squeezed, a turnaround or a loss-maker."""
    eps0, eps1, eps2 = row.get("eps0"), row.get("eps1"), row.get("eps2")
    eg1, rg1 = row.get("eg1"), row.get("rg1")
    gap = p["story_gap_pp"]
    out: list[str] = []
    if eps1 is not None and eps1 <= 0 and (eps2 is None or eps2 <= 0):
        out.append(
            "Loss-making in both forward years: a sales story (P/E and EPS targets are not meaningful)."
        )
    elif eps0 is not None and eps0 <= 0 and eps1 is not None and eps1 > 0:
        out.append("Turnaround: back to a profit this year after a loss (growth from a loss is not a rate).")
    elif eps1 is not None and eps1 > 0 and eps2 is not None and eps2 <= 0:
        out.append("Profits expected to turn into a loss next year.")
    elif eg1 is not None and rg1 is not None:
        if eg1 > 0 and rg1 > 0:
            if eg1 - rg1 >= gap:
                out.append(
                    f"Earnings-growth story: EPS +{eg1:.0f}% vs sales +{rg1:.0f}% this year, so margins are widening."
                )
            elif rg1 - eg1 >= gap:
                out.append(
                    f"Revenue-growth story: sales +{rg1:.0f}% vs EPS +{eg1:.0f}% this year, so margins are narrowing."
                )
            else:
                out.append(f"Balanced growth: EPS +{eg1:.0f}% and sales +{rg1:.0f}% this year.")
        elif eg1 < 0 < rg1:
            out.append(f"Margin squeeze: sales +{rg1:.0f}% but EPS {eg1:.0f}% this year.")
        elif rg1 < 0 < eg1:
            out.append(
                f"Cost story: EPS +{eg1:.0f}% while sales fall {abs(rg1):.0f}% this year (cuts, buybacks)."
            )
        elif eg1 < 0 and rg1 < 0:
            out.append(f"Shrinking: sales {rg1:.0f}% and EPS {eg1:.0f}% this year.")
    eg2, rg2 = row.get("eg2"), row.get("rg2")
    if eg2 is not None and eg1 is not None and eg1 > 0 and eg2 > 0:
        trend = "accelerating" if eg2 > eg1 else "slowing"
        out.append(f"EPS growth {trend} next year ({eg1:+.0f}% -> {eg2:+.0f}%).")
    if rg2 is not None and rg1 is not None and rg1 > 0 and rg2 > 0:
        out.append(
            f"Sales growth {'accelerating' if rg2 > rg1 else 'slowing'} next year ({rg1:+.0f}% -> {rg2:+.0f}%)."
        )
    return out


def gaap_gap(
    adj_eps0: float | None, shares: float | None, gaap_net_income: float | None, p: dict
) -> dict | None:
    """Consensus EPS is usually "adjusted" (non-GAAP). Adjusted EPS0 x today's share count against the GAAP net
    income the company filed with the SEC for the same fiscal year shows how much the adjustments add."""
    if adj_eps0 is None or not _pos(shares) or gaap_net_income is None:
        return None
    adj = adj_eps0 * shares
    if gaap_net_income <= 0:
        if adj <= 0:
            return {
                "adj_net_income": adj,
                "gap_pct": None,
                "text": "A loss on both GAAP and adjusted earnings.",
            }
        return {
            "adj_net_income": adj,
            "gap_pct": None,
            "text": "GAAP loss but an adjusted profit: the adjustments decide the story (check what is excluded).",
        }
    gap = (adj / gaap_net_income - 1) * 100
    if abs(gap) < p["gaap_gap_pct"]:
        text = f"Adjusted and GAAP earnings are close ({gap:+.0f}%)."
    elif gap > 0:
        text = (
            f"Adjusted earnings are {gap:.0f}% above GAAP: large non-GAAP adjustments "
            "(stock pay, amortisation, one-offs). Check what is excluded."
        )
    else:
        text = f"Adjusted earnings are {abs(gap):.0f}% below GAAP: GAAP includes one-off gains."
    return {"adj_net_income": adj, "gap_pct": gap, "text": text}
