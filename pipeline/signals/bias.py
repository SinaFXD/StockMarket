"""Combine signals into the portfolio bias (docs/02 "Combining into the portfolio bias").

Block score = mean of its available signals; bias = mean of the blocks that have any signal, so a block with
many series cannot dominate. Awaiting-data signals are left out. The website repeats this arithmetic in
JavaScript so manual overrides recalculate live (site/assets/macro.js).
"""

from __future__ import annotations

from typing import Any

BLOCKS = {
    "money_markets": "US money markets",
    "surveys": "US surveys",
    "prices_fx_equities": "Cyclical prices, FX & equities",
    "international": "International",
}
STATES = {"net_long": "Net long", "neutral": "Neutral (balanced)", "net_short": "Net short"}


def state_of(score: float | None, threshold: float) -> str | None:
    if score is None:
        return None
    return "net_long" if score >= threshold else "net_short" if score <= -threshold else "neutral"


def combine(signals: list[dict[str, Any]], threshold: float, overrides: dict[str, int] | None = None) -> dict:
    overrides = overrides or {}
    blocks = {}
    for key, label in BLOCKS.items():
        members = [s for s in signals if s["block"] == key]
        scores = [overrides.get(s["id"], s["score"]) for s in members]
        used = [x for x in scores if x is not None]
        blocks[key] = {
            "label": label,
            "score": round(sum(used) / len(used), 3) if used else None,
            "used": len(used),
            "total": len(members),
        }
    block_scores = [b["score"] for b in blocks.values() if b["score"] is not None]
    score = round(sum(block_scores) / len(block_scores), 3) if block_scores else None
    state = state_of(score, threshold)
    return {
        "score": score,
        "state": state,
        "label": STATES.get(state, "No reading"),
        "threshold": threshold,
        "blocks": blocks,
        "used": sum(b["used"] for b in blocks.values()),
        "total": len(signals),
    }


PRICE_ALERT_PREFIX = "Data vs prices:"
PRICE_ALERTS = {
    "data_weak_price_up": (
        f"{PRICE_ALERT_PREFIX} the bias is net short but the S&P 500 is in an uptrend (above its 200-day average "
        "and up over 3 months). Prices move before the reports: in 2019 and 2023 the market rose through weak data "
        "while the Fed reacted. Check what the market is pricing before going net short."
    ),
    "data_strong_price_down": (
        f"{PRICE_ALERT_PREFIX} the bias is net long but the S&P 500 is in a downtrend (below its 200-day average "
        "and down over 3 months). Prices may be discounting a slowdown the data does not show yet. Check what the "
        "market is pricing before adding net long exposure."
    ),
}


def price_alert(bias_state: str | None, sp500_score: int | None) -> str | None:
    """The leading data and the market's own trend point opposite ways (lesson 1: prices move before reports).
    Information only: the bias is not changed. site/assets/macro.js repeats this with the user's overrides."""
    if bias_state == "net_short" and sp500_score == 1:
        return "data_weak_price_up"
    if bias_state == "net_long" and sp500_score == -1:
        return "data_strong_price_down"
    return None


def alerts(signals: list[dict[str, Any]], bias: dict[str, Any], threshold: float) -> list[str]:
    """Disagreements between blocks and the cross-checks Anton asks for."""
    out = []
    sp = next((s for s in signals if s["id"] == "sp500"), None)
    if kind := price_alert(bias["state"], sp["score"] if sp else None):
        out.append(PRICE_ALERTS[kind])
    blocks = bias["blocks"]
    strong = {k: b for k, b in blocks.items() if b["score"] is not None and abs(b["score"]) >= threshold}
    pos = [b["label"] for b in strong.values() if b["score"] > 0]
    neg = [b["label"] for b in strong.values() if b["score"] < 0]
    if pos and neg:
        out.append(
            f"Blocks disagree: {', '.join(pos)} positive vs {', '.join(neg)} negative. "
            "Read them together (2019: weak surveys, supportive money markets, a Fed that cut)."
        )
    by_id = {s["id"]: s for s in signals}
    m2 = by_id.get("m2")
    others = [
        s["score"]
        for s in signals
        if s["block"] == "money_markets" and s["id"] != "m2" and s["score"] is not None
    ]
    mm = sum(others) / len(others) if others else None
    if m2 and m2["score"] is not None and mm is not None:
        if m2["score"] == 1 and mm > 0:
            out.append("M2 surge while bond markets look healthy: what does the Fed see that we don't?")
        elif m2["score"] == -1 and mm > 0:
            out.append("M2 shrinking while bond markets look healthy: the Fed is withdrawing liquidity.")
        elif m2["score"] == 1 and mm < 0:
            out.append(
                "M2 surge while bond markets are stressed: the Fed is leaning against tightening conditions."
            )
    for s in signals:
        for flag in s.get("flags", []):
            if flag.startswith(("Potential lie", "Junk moves first", "Short end inverted")):
                out.append(f"{s['name']}: {flag}")
    return out


def what_changed(now: dict[str, Any], before: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not before:
        return []
    prev = {s["id"]: s for s in before["signals"]}
    out = []
    if now["bias"]["state"] != before["bias"]["state"] or now["bias"]["score"] != before["bias"]["score"]:
        out.append(
            {
                "id": "bias",
                "name": "Portfolio bias",
                "from": before["bias"]["score"],
                "to": now["bias"]["score"],
                "from_state": before["bias"]["label"],
                "to_state": now["bias"]["label"],
            }
        )
    for s in now["signals"]:
        p = prev.get(s["id"])
        if p and (p["score"] != s["score"] or p["state"] != s["state"]):
            out.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    "from": p["score"],
                    "to": s["score"],
                    "from_state": p["state"],
                    "to_state": s["state"],
                }
            )
    return out
