"""Chart data and reading guides for the indicator pages."""

import json

import pandas as pd
from signal_helpers import TODAY, P, daily, frame, library, monthly

from pipeline.signals import build, charts


def test_every_signal_has_a_chart_builder_and_a_reading_guide():
    ids = {rule.__name__ for rule in build.RULES}
    assert ids == set(charts.BUILDERS)
    guides = charts.load_guides()
    for sid in ids:
        assert guides[sid]["what"] and guides[sid]["read"], sid


def test_daily_series_are_thinned_to_weekly_before_the_last_five_years():
    s = daily([("2010-01-04", 1.0), ("2026-10-20", 2.0)])
    t = charts.thin(s)
    recent = t[t.index >= "2021-10-21"]
    old = t[t.index < "2021-10-01"]
    assert len(recent) > 1200 and (old.index.to_series().diff().dropna().dt.days >= 7).all()
    m = monthly([1.0, 2.0, 3.0])
    assert charts.thin(m).equals(m)


def test_ism_panels_have_reference_lines_zones_and_components():
    df = frame(
        {"pmi": [49.0, 52.0], "new_orders": [50.0, 54.0], "inventories": [47.0, 48.0], "prices": [60.0, 62.0]}
    )
    panels = charts.ism_manufacturing(library(manual={"ism_manufacturing": df}).view(TODAY), P)
    head = panels[0]
    assert [s["name"] for s in head["series"]] == ["PMI", "New Orders"]
    assert head["refs"][0]["y"] == 50 and {z["tone"] for z in head["zones"]} == {"neg", "pos"}
    assert head["series"][0]["values"] == [49.0, 52.0] and head["series"][0]["dates"][-1] == "2026-09-01"
    grid = panels[-1]
    assert grid["kind"] == "grid" and [c["title"] for c in grid["charts"]] == ["Inventories", "Prices"]


def test_china_gap_panel_is_private_minus_official():
    df = frame({"ratingdog_manufacturing": [49.0, 51.0], "nbs_manufacturing": [50.5, 50.0]})
    panels = charts.china(library(manual={"china_pmi": df}).view(TODAY), P)
    assert panels[1]["series"][0]["values"] == [-1.5, 1.0]


def test_build_writes_one_file_per_indicator_even_without_data(tmp_path):
    lib = library(
        {
            "fred/T10Y2Y": (daily([("2016-01-04", 1.0), ("2026-10-20", 0.4)]), "daily"),
            "fred/M2SL": (monthly([100.0 + i for i in range(200)], last="2026-08"), "monthly"),
        }
    )
    build.build(tmp_path, TODAY, lib, start="2026-08")
    files = sorted(p.stem for p in (tmp_path / "macro" / "indicators").glob("*.json"))
    assert len(files) == 18
    curve = json.loads((tmp_path / "macro" / "indicators" / "curve.json").read_text())
    assert curve["guide"]["what"] and curve["panels"][0]["series"][0]["name"] == "10y-2y"
    nfib = json.loads((tmp_path / "macro" / "indicators" / "nfib.json").read_text())
    assert all(
        not p.get("series") for p in nfib["panels"] if p["kind"] == "line"
    )  # no data: empty panels, no crash
    assert pd.Timestamp(curve["panels"][0]["series"][0]["dates"][-1]) == pd.Timestamp("2026-10-20")
