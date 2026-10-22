"""Paths and tunable constants. Every threshold that is our choice (not Anton's) lives here."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MANUAL_DIR = DATA_DIR / "manual"
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
    "bias_threshold": 0.25,  # net long >= +0.25, net short <= -0.25 (tune)
}
# Monthly "as of" snapshots for the Macro Desk history and backtests start here.
SIGNAL_HISTORY_START = "2000-01"
