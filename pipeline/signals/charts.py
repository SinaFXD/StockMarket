"""Chart data for the indicator pages (``site/data/macro/indicators/<id>.json``).

Each indicator gets panels of same-unit series (never two y-axes: a second unit gets its own panel),
reference lines and shaded zones from docs/02, plus its reading guide. Daily series keep the last five
years at daily resolution and are thinned to weekly before that to keep the files small.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from ..store import write_json
from .base import monthly, window, yoy_monthly
from .data import View
from .surveys import NFIB_LEADING

log = logging.getLogger("pipeline.signals")
GUIDES_FILE = Path(__file__).with_name("guides.yaml")
DAILY_YEARS = 5


def thin(s: pd.Series) -> pd.Series:
    if len(s) < 2 or (s.index[1] - s.index[0]).days > 7:
        return s  # monthly or weekly already
    cut = s.index[-1] - pd.DateOffset(years=DAILY_YEARS)
    old = s[s.index < cut].resample("W-FRI").last().dropna()
    return pd.concat([old, s[s.index >= cut]])


def line(name: str, s: pd.Series, digits: int = 3) -> dict[str, Any]:
    s = thin(s.dropna())
    return {
        "name": name,
        "dates": [d.strftime("%Y-%m-%d") for d in s.index],
        "values": [round(float(v), digits) for v in s.to_numpy()],
    }


def panel(
    title: str, unit: str, series: list[dict], refs=(), zones=(), note: str | None = None
) -> dict[str, Any]:
    return {
        "kind": "line",
        "title": title,
        "unit": unit,
        "series": [x for x in series if x["values"]],
        "refs": [{"y": y, "label": label} for y, label in refs],
        "zones": [{"from": a, "to": b, "label": label, "tone": tone} for a, b, label, tone in zones],
        "note": note,
    }


def grid(title: str, unit: str, charts: list[dict]) -> dict[str, Any]:
    return {"kind": "grid", "title": title, "unit": unit, "charts": [c for c in charts if c["series"]]}


def _manual(v: View, file: str, col: str) -> pd.Series:
    return v.manual(file, col)


def _pct_lines(s: pd.Series, years: int, low: int, high: int) -> list[tuple[float, str]]:
    w = window(s, years)
    return [
        (round(float(w.quantile(low / 100)), 2), f"{low}th pct (10y)"),
        (round(float(w.quantile(high / 100)), 2), f"{high}th pct (10y)"),
    ]


# ------------------------------------------------------------------ builders ------------------------------------


def curve(v, p):
    return [
        panel(
            "Yield curve",
            "pp",
            [line("10y-2y", v.series("fred/T10Y2Y")), line("10y-3m", v.series("fred/T10Y3M"))],
            refs=[(0, "Inversion")],
            zones=[(0, p["curve_flat_max"], "Flat (0-0.5pp)", "neu")],
        )
    ]


def real_rate(v, p):
    y, cpi = v.series("fred/DGS10"), v.series("fred/CPIAUCSL")
    real = (monthly(y) - yoy_monthly(cpi)).dropna()
    out = [
        panel(
            "Real 10y rate (monthly)",
            "%",
            [line("10y yield - CPI YoY", real)],
            refs=[(0, "Zero"), *_pct_lines(real, p["percentile_years"], 25, 75)],
        ),
        panel(
            "10y yield and CPI inflation",
            "%",
            [line("10y yield", monthly(y)), line("CPI YoY", yoy_monthly(cpi))],
        ),
    ]
    vix = v.series("fred/VIXCLS")
    if not vix.empty:
        out.append(panel("VIX (compare with real rates)", "index", [line("VIX", monthly(vix))]))
    return out


def credit(v, p):
    return [
        panel(
            "CCC & lower high-yield spread",
            "%",
            [line("CCC OAS", v.series("fred/BAMLH0A3HYC"))],
            note="FRED publishes ICE spreads for about three years only.",
        ),
        panel(
            "BBB and AA corporate spreads",
            "%",
            [line("BBB OAS", v.series("fred/BAMLC0A4CBBB")), line("AA OAS", v.series("fred/BAMLC0A2CAA"))],
        ),
        panel("Moody's Baa minus 10y (long history)", "pp", [line("Baa-10y", v.series("fred/BAA10Y"))]),
    ]


def m2(v, p):
    s = v.series("fred/M2SL")
    mom = (s.pct_change() * 100).dropna()
    mean, sd = float(mom.mean()), float(mom.std())
    top = float(mom.quantile(p["m2_injection_pct"] / 100))
    return [
        panel(
            "M2 growth, month on month",
            "%",
            [line("MoM %", mom)],
            refs=[(round(mean, 2), "Average since 1959"), (round(top, 2), "Top 5% of months")],
            zones=[(mean - sd, mean + sd, "+-1 sigma", "neu")],
        ),
        panel("M2 growth, year on year", "%", [line("YoY %", yoy_monthly(s))], refs=[(0, "Shrinking below")]),
    ]


def vix(v, p):
    s = v.series("fred/VIXCLS") if not v.series("fred/VIXCLS").empty else v.series("yahoo/VIX")
    return [
        panel(
            "VIX",
            "index",
            [line("VIX", s)],
            refs=_pct_lines(s, p["percentile_years"], int(p["vix_low_pct"]), int(p["vix_high_pct"])),
        )
    ]


def ism_manufacturing(v, p):
    f = "ism_manufacturing"
    comps = [
        ("production", "Production"),
        ("employment", "Employment"),
        ("supplier_deliveries", "Supplier Deliveries"),
        ("inventories", "Inventories"),
        ("customers_inventories", "Customers' Inventories"),
        ("prices", "Prices"),
        ("backlog", "Backlog of Orders"),
        ("new_export_orders", "New Export Orders"),
        ("imports", "Imports"),
    ]
    return [
        panel(
            "PMI and New Orders",
            "index",
            [line("PMI", _manual(v, f, "pmi")), line("New Orders", _manual(v, f, "new_orders"))],
            refs=[(50, "50 = no change")],
            zones=[(40, p["ism_trough"], "Trough zone", "neg"), (p["ism_peak"], 62, "Near peak", "pos")],
        ),
        panel(
            "New Orders minus Inventories",
            "points",
            [
                line(
                    "New Orders - Inventories",
                    (_manual(v, f, "new_orders") - _manual(v, f, "inventories")).dropna(),
                )
            ],
            refs=[(0, "Orders = stock")],
        ),
        grid(
            "Components",
            "index",
            [panel(label, "index", [line(label, _manual(v, f, c))], refs=[(50, "50")]) for c, label in comps],
        ),
    ]


def ism_services(v, p):
    f = "ism_services"
    comps = [
        ("employment", "Employment"),
        ("supplier_deliveries", "Supplier Deliveries"),
        ("inventories", "Inventories"),
        ("prices", "Prices"),
        ("backlog", "Backlog of Orders"),
        ("new_export_orders", "New Export Orders"),
        ("imports", "Imports"),
        ("inventory_sentiment", "Inventory Sentiment"),
    ]
    return [
        panel(
            "Services PMI, Business Activity and New Orders",
            "index",
            [
                line("Services PMI", _manual(v, f, "pmi")),
                line("Business Activity", _manual(v, f, "business_activity")),
                line("New Orders", _manual(v, f, "new_orders")),
            ],
            refs=[(50, "50 = no change")],
            zones=[(40, 45, "Trough zone", "neg"), (58, 62, "Near peak", "pos")],
        ),
        grid(
            "Components",
            "index",
            [panel(label, "index", [line(label, _manual(v, f, c))], refs=[(50, "50")]) for c, label in comps],
        ),
    ]


def umich(v, p):
    since = "1978-01-01"
    ics, ice, icc = (v.series(k) for k in ("umich/ICS", "umich/ICE", "umich/ICC"))
    return [
        panel(
            "Consumer sentiment and its two halves",
            "index",
            [
                line("Sentiment", ics[ics.index >= since]),
                line("Expectations", ice[ice.index >= since]),
                line("Current conditions", icc[icc.index >= since]),
            ],
            refs=[(p["umich_pessimistic"], "70"), (p["umich_optimistic"], "80")],
            zones=[
                (p["umich_trough"], p["umich_pessimistic"], "Trough zone 55-70", "neg"),
                (p["umich_peak"], 110, "Peak zone 95-110", "pos"),
            ],
        )
    ]


def permits(v, p):
    s = v.series("fred/PERMIT")
    yoy = yoy_monthly(s)
    return [
        panel(
            "Building permits",
            "thousands, SAAR",
            [line("Permits", s, 0)],
            refs=[(p["permits_peak"], "2.0m peaks"), (p["permits_trough"], "Earlier troughs")],
            zones=[(p["permits_trend_low"], p["permits_trend_high"], "Long-run trend 1.3-1.4m", "neu")],
        ),
        panel(
            "Permits growth",
            "%",
            [line("YoY %", yoy), line("12-month average of YoY", yoy.rolling(12).mean())],
            refs=[(0, "Zero")],
        ),
    ]


def nfib(v, p):
    f = "nfib_sbet"
    parts = pd.concat([_manual(v, f, c) for c in NFIB_LEADING], axis=1).dropna()
    custom = parts.mean(axis=1)
    labels = {
        "plans_employment": "Plans to hire",
        "good_time_to_expand": "Good time to expand",
        "plans_inventories": "Plans to add inventory",
        "expect_economy_improve": "Expect economy to improve",
        "expect_real_sales_higher": "Expect higher real sales",
    }
    return [
        panel(
            "Small Business Optimism Index",
            "index",
            [line("Optimism", _manual(v, f, "optimism_index"))],
            refs=[(p["nfib_strong"], "100"), (p["nfib_weak"], "95")],
        ),
        panel(
            "ITPM leading index",
            "net %",
            [
                line("ITPM index", custom),
                line("4-month average", custom.rolling(int(p["nfib_ma_months"])).mean()),
            ],
        ),
        grid(
            "The five leading components",
            "net %",
            [
                panel(labels[c], "net %", [line(labels[c], _manual(v, f, c))], refs=[(0, "0")])
                for c in NFIB_LEADING
            ],
        ),
    ]


def _commodity(keys: list[str], title: str, unit: str):
    def build(v, p):
        key = max(keys, key=lambda k: v.series(k).index[-1] if not v.series(k).empty else pd.Timestamp.min)
        s = v.series(key)
        yoy = s.pct_change(periods=12 if v.lib.series[key].frequency == "monthly" else 252) * 100
        lim = p["commodity_yoy_pct"]
        return [
            panel(title, unit, [line(title, s, 2)]),
            panel(
                "Year-on-year change",
                "%",
                [line("YoY %", yoy.dropna(), 1)],
                refs=[(lim, f"+{lim:.0f}%"), (-lim, f"-{lim:.0f}%")],
            ),
        ]

    return build


def dollar(v, p):
    s = v.series("fred/DTWEXBGS")
    lim = p["dollar_yoy_pct"]
    return [
        panel("Broad trade-weighted dollar", "index", [line("Broad dollar", s, 2)]),
        panel(
            "Year-on-year change",
            "%",
            [line("YoY %", (s.pct_change(periods=252) * 100).dropna(), 1)],
            refs=[(lim, f"+{lim:.0f}% headwind"), (-lim, f"-{lim:.0f}%")],
        ),
    ]


def sp500(v, p):
    s = v.series("yahoo/GSPC")
    ma = s.rolling(int(p["sp500_ma_days"])).mean()
    return [
        panel(
            "S&P 500 and its 200-day average",
            "index",
            [line("S&P 500", s, 1), line("200-day average", ma, 1)],
        )
    ]


def esi(v, p):
    mid, z = p["esi_neutral"], p["esi_sd"] * p["esi_zone_sd"]
    countries = {"DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain", "NL": "Netherlands"}
    sectors = {
        "ICI": "Industry",
        "SCI": "Services",
        "CSMCI": "Consumers",
        "RCI": "Retail trade",
        "CCI": "Construction",
    }
    return [
        panel(
            "Euro-area Economic Sentiment Indicator",
            "index",
            [line("ESI", v.series("eurostat/ESI_EA"), 1)],
            refs=[(mid, "Long-term average")],
            zones=[(mid + z, mid + 2 * z, "Peak zone", "pos"), (mid - 2 * z, mid - z, "Trough zone", "neg")],
        ),
        grid(
            "Big countries: ESI",
            "index (100 = long-term average)",
            [
                panel(name, "index", [line(name, v.series(f"eurostat/ESI_{cc}"), 1)], refs=[(mid, "100")])
                for cc, name in countries.items()
            ],
        ),
        grid(
            "Euro-area sector confidence",
            "balance (% positive minus % negative answers)",
            [
                panel(name, "balance", [line(name, v.series(f"eurostat/{code}_EA"), 1)])
                for code, name in sectors.items()
            ],
        ),
    ]


def china(v, p):
    f = "china_pmi"
    rd, nbs = _manual(v, f, "ratingdog_manufacturing"), _manual(v, f, "nbs_manufacturing")
    return [
        panel(
            "Manufacturing PMI: private vs official",
            "index",
            [line("RatingDog (private)", rd), line("NBS (official)", nbs)],
            refs=[(50, "50")],
        ),
        panel(
            "Potential lie: private minus official",
            "points",
            [line("RatingDog - NBS", (rd - nbs).dropna())],
            refs=[(0, "Equal")],
        ),
        panel(
            "Services / non-manufacturing",
            "index",
            [
                line("RatingDog services", _manual(v, f, "ratingdog_services")),
                line("NBS non-manufacturing", _manual(v, f, "nbs_non_manufacturing")),
            ],
            refs=[(50, "50")],
        ),
        panel(
            "China real 10y rate (context, not scored)",
            "%",
            [line("10y yield - CPI YoY", (v.series("oecd/Y10_CN") - v.series("oecd/CPI_CN")).dropna())],
            refs=[(0, "Zero")],
            note="China's bonds are mostly held at home, so this is a weak leading indicator (lesson 14).",
        ),
    ]


def intl_money_markets(v, p):
    from .international import COUNTRIES, SCORED  # avoid an import cycle at module load

    real, curves = [], []
    for cc in SCORED:
        y, short, cpi = (v.series(f"oecd/{k}_{cc}") for k in ("Y10", "RATE", "CPI"))
        r = (y - cpi).dropna()
        refs = [(0, "0")] + (_pct_lines(r, p["percentile_years"], 25, 75) if len(r) > 24 else [])
        real.append(panel(COUNTRIES[cc], "%", [line("Real 10y", r)], refs=refs))
        curves.append(
            panel(
                COUNTRIES[cc],
                "pp",
                [line("10y - short rate", (y - short).dropna())],
                refs=[(0, "Inversion")],
                zones=[(0, p["curve_flat_max"], "Flat", "neu")],
            )
        )
    it, de = v.series("oecd/Y10_IT"), v.series("oecd/Y10_DE")
    return [
        grid(
            "Real 10y rates (10y yield - CPI YoY); lines at 0 and the 25th/75th percentiles of 10 years",
            "%",
            real,
        ),
        grid("Yield curves (10y yield - overnight rate); grey band = flat (0-0.5pp)", "pp", curves),
        panel(
            "Italy minus Germany 10y yield",
            "pp",
            [line("Italy - Germany", (it - de).dropna())],
            note="Shown for context, not scored: a widening spread has marked euro-area stress (2011-12).",
        ),
    ]


BUILDERS = {
    "curve": curve,
    "real_rate": real_rate,
    "credit": credit,
    "m2": m2,
    "vix": vix,
    "ism_manufacturing": ism_manufacturing,
    "ism_services": ism_services,
    "umich": umich,
    "permits": permits,
    "nfib": nfib,
    "brent": _commodity(["fred/DCOILBRENTEU", "yahoo/BZ_F"], "Brent crude", "$ per barrel"),
    "copper": _commodity(["yahoo/HG_F", "fred/PCOPPUSDM"], "Copper", "price"),
    "iron_ore": _commodity(["fred/PIORECRUSDM"], "Iron ore", "$ per tonne"),
    "lumber": _commodity(["fred/WPU081"], "Lumber PPI", "index"),
    "dollar": dollar,
    "sp500": sp500,
    "esi": esi,
    "china": china,
    "intl_money_markets": intl_money_markets,
}


def load_guides() -> dict[str, dict]:
    return yaml.safe_load(GUIDES_FILE.read_text(encoding="utf-8"))


def build_charts(view: View, params: dict, out_dir: Path, signal_ids: list[str]) -> int:
    guides = load_guides()
    written = 0
    for sid in signal_ids:
        try:
            panels = BUILDERS[sid](view, params)
        except Exception:  # a broken chart must not stop the others; the page shows "no chart data"
            log.exception("chart %s failed", sid)
            panels = []
        write_json(
            out_dir / f"{sid}.json", {"id": sid, "guide": guides.get(sid, {}), "panels": panels}, indent=None
        )
        written += 1
    return written
