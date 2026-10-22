"""Coincident and lagging confirmers (lessons 1-3, 15): ``site/data/macro/confirmers.json``.

Leading indicators set the bias; coincident data (jobs, claims, production, orders, inflation) and lagging data
(GDP, corporate profits) confirm or contradict it later. They are shown next to the bias, **never scored**: a
lagging series that turns has usually been anticipated by prices already.

Each growth confirmer gets a tone (+1 supports expansion, -1 signals weakness, 0 neither) from thresholds in
``config.CONFIRMERS`` (all "tune"); inflation is shown with its direction only.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..config import CONFIRMERS as C
from .base import fmt, iso, months_back, yoy_monthly
from .data import View


def _item(cid: str, name: str, kind: str, key: str, s: pd.Series, **kw: Any) -> dict[str, Any]:
    return {
        "id": cid,
        "name": name,
        "kind": kind,
        "source": key,
        "as_of": iso(s.index[-1]) if not s.empty else None,
        "tone": None,
        "value": None,
        "unit": "",
        "text": "",
        **kw,
    }


def _tone(x: float | None, good: float, bad: float, higher_is_better: bool = True) -> int:
    if x is None:
        return 0
    if higher_is_better:
        return 1 if x >= good else -1 if x <= bad else 0
    return 1 if x <= good else -1 if x >= bad else 0


def _quarterly_pct(s: pd.Series, lag: int) -> float | None:
    if len(s) <= lag:
        return None
    return (float(s.iloc[-1]) / float(s.iloc[-1 - lag]) - 1) * 100


def _weekly_avg_change(s: pd.Series) -> float | None:
    """4-week average vs the 4-week average 13 weeks earlier, in %."""
    avg = s.rolling(4).mean().dropna()
    if len(avg) < 14:
        return None
    return (float(avg.iloc[-1]) / float(avg.iloc[-14]) - 1) * 100


def growth_items(v: View) -> list[dict[str, Any]]:
    out = []
    key = "fred/PAYEMS"
    s = v.series(key)
    if len(s) > 3:
        avg = (float(s.iloc[-1]) - float(s.iloc[-4])) / 3
        out.append(
            _item(
                "payrolls",
                "Nonfarm payrolls",
                "coincident",
                key,
                s,
                value=avg,
                unit="k / month (3m avg)",
                tone=_tone(avg, C["payrolls_good_k"], C["payrolls_bad_k"]),
                text=f"Jobs grew by {avg:+.0f}k a month over the last 3 months.",
            )
        )
    key = "fred/UNRATE"
    s = v.series(key)
    if len(s) > 3:
        ch = float(s.iloc[-1]) - float(s.iloc[-4])
        out.append(
            _item(
                "unemployment",
                "Unemployment rate",
                "coincident",
                key,
                s,
                value=float(s.iloc[-1]),
                unit="%",
                tone=_tone(ch, -C["unemployment_move_pp"], C["unemployment_move_pp"], higher_is_better=False),
                text=f"{s.iloc[-1]:.1f}%, {ch:+.1f}pp over 3 months.",
            )
        )
    for cid, name, k in (
        ("claims", "Initial jobless claims", "ICSA"),
        ("cont_claims", "Continuing claims", "CCSA"),
    ):
        key = f"fred/{k}"
        s = v.series(key)
        ch = _weekly_avg_change(s)
        if ch is not None:
            avg = float(s.rolling(4).mean().iloc[-1])
            out.append(
                _item(
                    cid,
                    name,
                    "coincident",
                    key,
                    s,
                    value=avg / 1000,
                    unit="k (4-week avg)",
                    tone=_tone(ch, -C["claims_move_pct"], C["claims_move_pct"], higher_is_better=False),
                    text=f"4-week average {avg / 1000:.0f}k, {ch:+.1f}% vs 13 weeks earlier.",
                )
            )
    key = "fred/INDPRO"
    s = v.series(key)
    yoy = yoy_monthly(s) if len(s) > 13 else pd.Series(dtype=float)
    if not yoy.empty:
        x = float(yoy.iloc[-1])
        out.append(
            _item(
                "industrial_production",
                "Industrial production",
                "coincident",
                key,
                s,
                value=x,
                unit="% YoY",
                tone=_tone(x, C["production_yoy_pct"], -C["production_yoy_pct"]),
                text=f"{x:+.1f}% on a year earlier.",
            )
        )
    key = "fred/DGORDER"
    s = v.series(key)
    if len(s) > 15:
        three = s.rolling(3).sum().dropna()
        yoy3 = yoy_monthly(three)
        if not yoy3.empty:
            x = float(yoy3.iloc[-1])
            out.append(
                _item(
                    "durable_goods",
                    "Durable goods orders",
                    "coincident",
                    key,
                    s,
                    value=x,
                    unit="% YoY (3 months)",
                    tone=_tone(x, C["orders_yoy_pct"], -C["orders_yoy_pct"]),
                    text=f"Last 3 months {x:+.1f}% on a year earlier.",
                )
            )
    key = "fred/GDPC1"
    s = v.series(key)
    q = _quarterly_pct(s, 1)
    if q is not None:
        ann = ((1 + q / 100) ** 4 - 1) * 100
        y = _quarterly_pct(s, 4)
        out.append(
            _item(
                "gdp",
                "Real GDP",
                "lagging",
                key,
                s,
                value=ann,
                unit="% q/q annualised",
                tone=_tone(ann, C["gdp_good_pct"], C["gdp_bad_pct"]),
                text=f"{ann:+.1f}% annualised last quarter ({fmt(y, 1, True)}% on a year earlier).",
            )
        )
    key = "fred/CP"
    s = v.series(key)
    y = _quarterly_pct(s, 4)
    if y is not None:
        out.append(
            _item(
                "profits",
                "Corporate profits (after tax)",
                "lagging",
                key,
                s,
                value=y,
                unit="% YoY",
                tone=_tone(y, C["profits_yoy_pct"], 0.0),
                text=f"{y:+.1f}% on a year earlier.",
            )
        )
    return out


def inflation_items(v: View) -> list[dict[str, Any]]:
    out = []
    for cid, name, k in (
        ("cpi", "CPI inflation", "CPIAUCSL"),
        ("core_cpi", "Core CPI inflation", "CPILFESL"),
        ("ppi", "PPI final demand", "PPIFIS"),
    ):
        key = f"fred/{k}"
        s = v.series(key)
        yoy = yoy_monthly(s) if len(s) > 16 else pd.Series(dtype=float)
        if yoy.empty:
            continue
        x, then = float(yoy.iloc[-1]), months_back(yoy, 3)
        ch = None if then is None else x - then
        direction = (
            "steady" if ch is None or abs(ch) < C["inflation_move_pp"] else "rising" if ch > 0 else "falling"
        )
        out.append(
            _item(
                cid,
                name,
                "coincident",
                key,
                s,
                value=x,
                unit="% YoY",
                direction=direction,
                text=f"{x:.1f}% on a year earlier, {direction} ({fmt(ch, 1, True)}pp over 3 months).",
            )
        )
    return out


def summary(items: list[dict[str, Any]], bias: dict[str, Any]) -> dict[str, Any]:
    tones = [i["tone"] for i in items if i["tone"] is not None]
    up, down = tones.count(1), tones.count(-1)
    state = bias.get("state")
    if not tones:
        text = "No confirmer data yet."
    else:
        balance = "firm" if up > down else "weak" if down > up else "mixed"
        text = f"Coincident and lagging data look {balance}: {up} supportive, {down} weak, {len(tones) - up - down} neutral."
        if (state == "net_long" and down > up) or (state == "net_short" and up > down):
            text += (
                " They disagree with the leading bias. Leading indicators turn first, so this can be an early turn; "
                "check which blocks drive the bias before acting."
            )
        elif state in ("net_long", "net_short"):
            text += " They agree with the leading bias."
    return {"supportive": up, "weak": down, "total": len(tones), "text": text, "bias_state": state}


def build_confirmers(v: View, bias: dict[str, Any]) -> dict[str, Any]:
    growth = growth_items(v)
    return {
        "as_of": v.as_of.isoformat(),
        "growth": growth,
        "inflation": inflation_items(v),
        "summary": summary(growth, bias),
        "thresholds": C,
    }
