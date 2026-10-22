"""Forward test of the Screener's types: weekly cohorts, returns filled when due, long-short spread statistics."""

import json

import pandas as pd
import pytest

from pipeline.forward import build, outliers

DAYS = [d.date().isoformat() for d in pd.bdate_range("2026-10-01", periods=80)]


def screener_row(t, cls, sector="Technology", vol_ok=True):
    return {"t": t, "cls": cls, "sector": sector, "vol_ok": vol_ok}


def path(start, step):
    return {d: start * (1 + step) ** i for i, d in enumerate(DAYS)}


PRICES = {"UP": path(100, 0.01), "DOWN": path(100, -0.01), "FLAT": path(50, 0.0)}


def closes(t):
    return PRICES.get(t, {})


def test_one_cohort_per_iso_week_and_only_candidate_types():
    log = []
    rows = [screener_row("UP", "positive"), screener_row("DOWN", "negative"), screener_row("FLAT", "boring"),
            screener_row("NOPRICE", "positive")]  # fmt: skip
    assert outliers.add_cohort(log, DAYS[0], rows, closes) == 2
    assert {r["ticker"] for r in log} == {"UP", "DOWN"} and log[0]["entry"] == 100.0
    assert outliers.add_cohort(log, DAYS[1], rows, closes) == 0  # same ISO week
    assert outliers.add_cohort(log, DAYS[5], rows, closes) == 2  # next week


def test_returns_are_filled_only_when_the_horizon_has_passed():
    log = []
    outliers.add_cohort(
        log, DAYS[0], [screener_row("UP", "positive"), screener_row("DOWN", "negative")], closes
    )
    spy = path(400, 0.005)
    etfs = {"XLK": path(200, 0.002)}
    filled = outliers.fill(log, DAYS[:30], closes, spy, etfs, {"Technology": "XLK"}.get)
    up = next(r for r in log if r["ticker"] == "UP")
    assert filled == 2 and up["r40"] is None and up["r60"] is None
    assert up["r20"] == pytest.approx((1.01**20 - 1) * 100)
    assert up["spy20"] == pytest.approx((1.005**20 - 1) * 100) and up["etf20"] == pytest.approx(
        (1.002**20 - 1) * 100
    )
    assert outliers.fill(log, DAYS, closes, spy, etfs, {"Technology": "XLK"}.get) == 4  # 40 and 60 now
    assert outliers.fill(log, DAYS, closes, spy, etfs, {"Technology": "XLK"}.get) == 0  # never twice


def test_a_missing_day_uses_the_last_close_within_five_days():
    series = {"2026-10-01": 10.0, "2026-10-05": 11.0}
    assert outliers._close_on(series, "2026-10-07") == 11.0
    assert outliers._close_on(series, "2026-10-20") is None


def test_csv_round_trip():
    log = []
    outliers.add_cohort(log, DAYS[0], [screener_row("UP", "positive", vol_ok=None)], closes)
    outliers.fill(log, DAYS, closes, path(400, 0.0), {}, lambda s: None)
    back = outliers.read(outliers.write(log))
    assert back[0]["vol_ok"] is None and back[0]["r20"] == pytest.approx(log[0]["r20"], abs=1e-3)
    assert back[0]["etf20"] is None and back[0]["spy20"] == 0.0


def test_summary_spread_and_independent_windows():
    log = []
    rows = [screener_row("UP", "positive"), screener_row("DOWN", "negative", vol_ok=False)]
    for i in range(0, 50, 5):  # ten weekly cohorts
        outliers.add_cohort(log, DAYS[i], rows, closes)
    outliers.fill(log, DAYS, closes, path(400, 0.0), {}, lambda s: None)
    s = outliers.summary(log)
    h20 = s["horizons"]["20"]
    assert s["cohorts"] == 10 and h20["spread"]["n_cohorts"] == 10 and h20["spread"]["n_independent"] == 2.5
    spread = (1.01**20 - 1) * 100 - (0.99**20 - 1) * 100
    assert h20["spread"]["mean"] == pytest.approx(spread, abs=1e-3) and h20["spread"]["pct_pos"] == 100.0
    assert (
        h20["types"]["positive"]["vs_spy"]["pct_pos"] == 100.0
        and h20["types"]["negative"]["return"]["n"] == 10
    )
    only = outliers.summary(log, vol_only=True)
    assert only["horizons"]["20"]["types"]["negative"]["return"]["n"] == 0
    assert only["horizons"]["20"]["spread"]["n_cohorts"] == 0


def test_due_tickers():
    log = []
    outliers.add_cohort(
        log, DAYS[0], [screener_row("UP", "positive"), screener_row("DOWN", "negative")], closes
    )
    assert outliers.due_tickers(log, DAYS[:10], lambda t: False) == []  # nothing due yet
    assert outliers.due_tickers(log, DAYS, lambda t: t == "UP") == ["DOWN"]


def test_run_writes_the_record_and_prices_stocks_that_left(tmp_path):
    site = tmp_path / "site"
    for sym, start in [("SPY", 400), ("XLK", 200)]:
        p = site / "series" / "yahoo" / f"{sym}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        obs = [[d, v, v] for d, v in path(start, 0.0).items()]
        p.write_text(json.dumps({"columns": ["date", "close", "adj_close"], "observations": obs}))

    class Builder:
        rows = [screener_row("UP", "positive"), screener_row("GONE", "negative")]

        def bars(self):
            return {
                "UP": {"d": DAYS, "c": list(PRICES["UP"].values())},
                "GONE": {"d": DAYS, "c": list(PRICES["DOWN"].values())},
            }

    st = build.run(site, Builder(), site, offline=True)
    assert st["status"] == "ok" and st["rows"] == 2  # the cohort day is the latest bar

    # next run: GONE has left the universe; its price comes from the extra download
    class Later(Builder):
        rows = []

        def bars(self):
            return {"UP": {"d": DAYS, "c": list(PRICES["UP"].values())}}

    rows = outliers.read((site / "forward" / "outliers.csv").read_text())
    assert rows[0]["cohort"] == DAYS[-1]
    # rewrite the record with an older cohort so its horizons are due
    for r in rows:
        r["cohort"] = DAYS[0]
        r["entry"] = 100.0
    (site / "forward" / "outliers.csv").write_text(outliers.write(rows))
    frames = {"GONE": pd.DataFrame({"Close": list(PRICES["DOWN"].values())}, index=pd.to_datetime(DAYS))}
    st = build.run(
        site, Later(), site, offline=False, download=lambda tickers: {t: frames[t] for t in tickers}
    )
    rows = {r["ticker"]: r for r in outliers.read((site / "forward" / "outliers.csv").read_text())}
    assert st["filled"] == 6 and rows["GONE"]["r20"] == pytest.approx((0.99**20 - 1) * 100, abs=1e-3)
    summary = json.loads((site / "forward" / "summary.json").read_text())
    assert summary["all"]["horizons"]["60"]["spread"]["n_cohorts"] == 1 and summary["missing_prices"] == 0
    assert build.run(tmp_path / "empty", Later(), tmp_path / "empty")["status"] == "failed"


def rev_row(t, rev, sector="Technology", cls="boring", vol_ok=True):
    return {"t": t, "cls": cls, "sector": sector, "vol_ok": vol_ok, "eps1_rev90": rev}


def test_revision_groups_are_the_top_and_bottom_quarter_of_each_sector():
    rows = [rev_row(f"T{i}", float(i)) for i in range(8)]  # 0..7: quarter = 2 stocks
    rows += [rev_row("SMALL1", 50.0, "Energy"), rev_row("SMALL2", -50.0, "Energy")]  # too few in Energy
    rows += [rev_row("NONE", None)]
    g = outliers.revision_groups(rows)
    assert g == {"T0": "down", "T1": "down", "T6": "up", "T7": "up"}
    flat = outliers.revision_groups([rev_row(f"F{i}", 1.0) for i in range(8)])
    assert flat == {}  # all equal: nobody is up or down


def test_cohort_adds_revision_groups_and_keeps_their_numbers():
    prices = {f"T{i}": {DAYS[0]: 10.0} for i in range(8)}
    rows = [rev_row(f"T{i}", float(i), cls="positive" if i == 3 else "boring") for i in range(8)]
    log = []
    assert outliers.add_cohort(log, DAYS[0], rows, lambda t: prices.get(t, {})) == 5  # 4 grouped + 1 positive
    by = {r["ticker"]: r for r in log}
    assert by["T7"]["rev_group"] == "up" and by["T7"]["type"] == "boring" and by["T7"]["rev90"] == 7.0
    assert by["T3"]["rev_group"] is None and by["T3"]["type"] == "positive"
    back = {r["ticker"]: r for r in outliers.read(outliers.write(log))}
    assert (
        back["T0"]["rev_group"] == "down" and back["T0"]["rev90"] == 0.0 and back["T3"]["rev_group"] is None
    )


def test_an_old_record_without_revision_columns_still_reads():
    old = "cohort,ticker,type,sector,vol_ok,entry,r20,spy20,etf20,r40,spy40,etf40,r60,spy60,etf60\n"
    old += "2026-10-01,UP,positive,Technology,1,100.0000,5.000,1.000,,,,,,,\n"
    r = outliers.read(old)[0]
    assert r["rev_group"] is None and r["rev90"] is None and r["r20"] == 5.0


def test_revision_spreads_h1_and_h2():
    log = []
    for c in range(0, 50, 5):  # ten weekly cohorts
        for t, cls, grp, step in [("A", "positive", "up", 0.01), ("B", "positive", None, 0.0),
                                  ("C", "boring", "down", -0.01)]:  # fmt: skip
            p = path(100, step)
            log.append({"cohort": DAYS[c], "ticker": t, "type": cls, "sector": "Technology", "vol_ok": True,
                        "entry": p[DAYS[c]], "rev90": 1.0, "rev_group": grp,
                        **{k: None for k in outliers.RETURNS}})  # fmt: skip
    series = {"A": path(100, 0.01), "B": path(100, 0.0), "C": path(100, -0.01)}
    outliers.fill(log, DAYS, lambda t: series[t], path(400, 0.0), {}, lambda s: None)
    h20 = outliers.summary(log)["horizons"]["20"]
    up, down = (1.01**20 - 1) * 100, (0.99**20 - 1) * 100
    assert (
        h20["rev_spread"]["mean"] == pytest.approx(up - down, abs=1e-3)
        and h20["rev_spread"]["n_cohorts"] == 10
    )
    assert h20["positive_rev_spread"]["mean"] == pytest.approx(up, abs=1e-3)  # A vs B (flat)
    assert (
        h20["revisions"]["down"]["return"]["n"] == 10 and h20["revisions"]["up"]["vs_spy"]["pct_pos"] == 100.0
    )
    assert h20["spread"]["n_cohorts"] == 0  # no negative outliers in this record


def test_cohort_day_is_the_last_day_spy_has_closed(tmp_path):
    site = tmp_path / "site"
    p = site / "series" / "yahoo" / "SPY.json"
    p.parent.mkdir(parents=True)
    obs = [[d, 400.0, 400.0] for d in DAYS[:-1]]  # SPY leaves out today's unfinished session
    p.write_text(json.dumps({"columns": ["date", "close", "adj_close"], "observations": obs}))

    class Builder:
        rows = [screener_row("UP", "positive")]

        def bars(self):
            return {"UP": {"d": DAYS, "c": list(PRICES["UP"].values())}}

    st = build.run(site, Builder(), site, offline=True)
    rows = outliers.read((site / "forward" / "outliers.csv").read_text())
    assert (
        st["added"] == 1
        and rows[0]["cohort"] == DAYS[-2]
        and rows[0]["entry"] == pytest.approx(PRICES["UP"][DAYS[-2]])
    )
