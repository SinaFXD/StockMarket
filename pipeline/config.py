"""Paths and tunable constants. Every threshold that is our choice (not Anton's) lives here."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MANUAL_DIR = DATA_DIR / "manual"
IDEAS_DIR = DATA_DIR / "ideas"
SITE_DIR = ROOT / "site"
SITE_DATA_DIR = SITE_DIR / "data"
CATALOG_FILE = PACKAGE_DIR / "catalog.yaml"

REPO_URL = "https://github.com/SinaFXD/StockMarket"
USER_AGENT = f"PTM-Fundamental-Dashboard/0.1 (+{REPO_URL})"

# FRED allows 120 requests per minute per key; stay comfortably below it.
FRED_MIN_INTERVAL_S = 0.55
YAHOO_MIN_INTERVAL_S = 0.4

# A series is "stale" when its last observation is older than this many calendar days.
# Generous on purpose: they must absorb publication lags and holidays, and only catch a source that
# stopped updating. Per-series overrides live in catalog.yaml (max_age_days).
MAX_AGE_DAYS = {
    "daily": 10,
    "weekly": 21,
    "monthly": 100,
    "quarterly": 250,
    "annual": 500,
}

# Manual data: after a report's release date, the missing month is "due" for this many days, then the
# indicator becomes "awaiting data" (shown with its last date and excluded from scores).
MANUAL_GRACE_DAYS = 5

# ---------------------------------------------------------------------------------------------------------
# Phase 1 Macro Desk: first-reading rules from docs/02-indicator-rules.md. Numbers from Anton are labelled;
# every other number is our own first choice ("tune") and is recorded in docs/02.
SIGNALS: dict[str, float] = {
    "lookback_days": 91,  # "over 3 months" (tune)
    "percentile_years": 10,
    "curve_flat_max": 0.5,  # docs/02: flat = 0-0.5pp (tune)
    "curve_stable_band": 0.10,  # 3m change smaller than this is neither steepening nor flattening (tune)
    "real_rate_low_pct": 25,  # tune
    "real_rate_high_pct": 75,  # tune
    "credit_wide_pct": 90,  # 3m change in OAS above its 90th percentile = widening fast (tune)
    "credit_tight_pct": 10,  # tune
    "credit_min_history_days": 365,  # less ICE history than this -> use Moody's Baa-10y instead
    "m2_injection_pct": 95,  # Chris Coyle: ~5% of months above ~1.15% MoM = abnormal injection
    "vix_high_pct": 75,  # tune
    "vix_low_pct": 25,  # tune
    "ism_neutral": 50,  # Anton
    "ism_peak": 58,  # Anton: peaks ~60 (flag at 58, tune)
    "ism_trough": 45,  # Anton: troughs 40-45
    "umich_expectations_drop": -10,  # 3m change in Expectations (tune)
    "umich_pessimistic": 70,  # Anton: 55-70 pessimistic
    "umich_optimistic": 80,  # Anton: several readings > 80 optimistic
    "umich_several": 3,  # "several readings" = 3 months (tune)
    "umich_peak": 95,  # Anton: 95-110 peak zone
    "umich_trough": 55,
    "permits_trend_low": 1300,  # Anton: long-run trend 1.3-1.4m (thousands, SAAR)
    "permits_trend_high": 1400,
    "permits_peak": 2000,  # Anton: >= 2m peaks
    "permits_trough": 800,  # Anton: 700-800k troughs in earlier cycles
    "nfib_strong": 100,  # Anton
    "nfib_weak": 95,  # Anton
    "nfib_ma_months": 4,  # Anton: 4-month moving average of the custom index
    "nfib_falling_months": 3,  # docs/02
    "commodity_yoy_pct": 5.0,  # tune
    "dollar_yoy_pct": 5.0,  # tune
    "sp500_ma_days": 200,  # tune (rule proposed in docs/02)
    "esi_neutral": 100,  # Eurostat: long-term average 100, SD 10
    "esi_sd": 10,
    "esi_zone_sd": 1.5,  # peak/trough zone flags (tune)
    "china_neutral": 50,
    "intl_net": 2,  # international money markets: net of the four country scores to count (tune)
    "intl_min_countries": 3,  # fewer countries with data -> awaiting (tune)
    "bias_threshold": 0.25,  # net long >= +0.25, net short <= -0.25 (tune)
}
# Coincident & lagging confirmers (shown, never scored). Tone thresholds are all our choice (tune), except the
# 2% GDP growth line, which follows Anton's "GDP >= 2% = optimistic" band in lesson 9.
CONFIRMERS: dict[str, float] = {
    "payrolls_good_k": 100.0,  # 3-month average monthly change, thousands
    "payrolls_bad_k": 0.0,
    "unemployment_move_pp": 0.2,  # 3-month change
    "claims_move_pct": 10.0,  # 4-week average vs 13 weeks earlier
    "production_yoy_pct": 1.0,
    "orders_yoy_pct": 3.0,
    "gdp_good_pct": 2.0,  # annualised q/q
    "gdp_bad_pct": 0.0,
    "profits_yoy_pct": 5.0,
    "inflation_move_pp": 0.2,  # 3-month change in YoY that counts as rising/falling
}

# Phase 2 Sector Screener (lessons 22-29). Every number here is our choice (tune) unless marked otherwise.
SCREENER: dict[str, float] = {
    "min_market_cap": 2e9,  # universe filter: ~2,100 US-listed stocks (Anton: a universe of ~2,200+)
    "summary_max_age_hours": 20,  # re-download a stock's estimates when older than this
    "summary_budget": 2500,  # at most this many estimate downloads per run (CI passes a small number)
    "summary_fail_stop": 25,  # stop downloading after this many failures in a row (Yahoo throttling)
    "stale_estimates_days": 10,  # estimates older than this are flagged
    "min_analysts": 3,  # fewer analysts behind the EPS estimates -> flagged
    "extreme_growth_pct": 300,  # |EPS growth| above this -> flagged "check"
    "extreme_pe": 200,  # P/E above this -> flagged "check"
    "feed_mismatch_pct": 25,  # Yahoo's two estimate feeds disagree by more than this -> excluded
    # 2b outliers: positions within the stock's sector (percentiles of clean stocks)
    "top_pct": 75,  # EG1 and EG2 both at or above -> positive outlier (tune)
    "bottom_pct": 25,  # both at or below, and negative -> negative outlier (tune)
    "min_peers": 10,  # fewer clean stocks in a sector -> compare with the whole universe
    # 2b volatility filter (Anton: realised and implied roughly >= 1.5x VIX)
    "vol_vs_vix": 1.5,
    "rv_days": 63,  # realised volatility over ~3 months of trading days (the 1-3 month horizon)
    "atr_days": 14,
    "iv_target_days": 45,  # option expiry closest to the middle of the 20-60 day horizon
    "iv_budget": 400,  # at most this many option chains per run (candidates first)
    "iv_pause_s": 0.3,  # pause between option downloads (Yahoo throttles bursts)
    "price_chunk": 200,  # tickers per batch price download
    "chart_days": 260,  # daily bars kept per stock for the trade-idea chart (~1 year: 200-day average)
}

# Phase 3: Trade Idea Workbench (lessons 30-33). Rules recorded in docs/08-workbench-method.md.
WORKBENCH: dict[str, float] = {
    "horizon_days": 40,  # default horizon of a new idea, calendar days (the course's window is 20-60)
    "horizon_min": 20,
    "horizon_max": 60,
    "sigma_ok": 1.0,  # target within a 1-sigma move over the horizon: realistic (tune)
    "sigma_stretched": 2.0,  # beyond 2 sigma: unrealistic for the horizon, adjust the target (tune)
    "story_gap_pp": 5,  # EPS vs sales growth gap (percentage points) that makes it an earnings/revenue story
    "gaap_gap_pct": 15,  # adjusted (consensus) vs GAAP net income gap worth a warning (tune)
    "short_crowded_pct": 10,  # short interest above this % of float: a crowded short (tune)
    "short_crowded_days": 5,  # or more days to cover than this (tune)
    "short_change_pct": 10,  # change in shares short vs the prior month worth mentioning
    "review_days": 7,  # an idea not updated for this many days is due for review (tune)
    "stale_days": 14,  # ... and stale after this many (tune)
    "pipeline_min": 10,  # Anton: keep a pipeline of 10-15 ideas
    "pipeline_max": 15,
    "ideas_per_week": 2,  # Anton: about two new ideas a week
}

# Monthly "as of" snapshots for the Macro Desk history and backtests start here.
SIGNAL_HISTORY_START = "2000-01"
